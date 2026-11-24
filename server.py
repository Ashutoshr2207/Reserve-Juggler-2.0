"""Loopback-only web application. Run: python server.py --port 8000."""

import argparse
import csv
import io
import json
import logging
import mimetypes
import os
import secrets
import sqlite3
import threading
from datetime import timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from liquidity_forecasting.assistant import (
    AssistantError,
    answer,
    decision_context,
    validate_request,
)
from liquidity_forecasting.auth import (
    AuthError,
    AuthManager,
)
from liquidity_forecasting.ml_shadow import capture_inputs, diagnostics
from liquidity_forecasting.planning import analyze, moment, scheduled
from liquidity_forecasting.treasury import (
    apply_action,
    initial_state,
    reserve_plan,
    sample_history,
    snapshot,
    validate_policy,
)

ROOT = Path(__file__).resolve().parent
ASSISTANT_SLOTS = threading.BoundedSemaphore(4)


def load_env_file():
    """Load development environment variables from local .env if present."""
    env_path = ROOT / ".env"
    if env_path.is_file():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, v = stripped.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception as err:
            logging.debug("Could not read .env: %s", err)


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, state TEXT)"
        )
        self.connection.commit()

    def read(self, key):
        row = self.connection.execute(
            "SELECT state FROM workspaces WHERE id = ?", (key,)
        ).fetchone()
        if row:
            state = json.loads(row[0])
            if state.get("currency") != "INR":
                self.write(key + ":legacy-usd", state)
                revision = state["revision"] + 1
                state = initial_state()
                state["revision"] = revision
                state["migration_note"] = (
                    "New INR demo created. Previous USD workspace preserved locally; "
                    "no currency conversion was performed."
                )
                self.write(key, state)
            state.setdefault("scheduled", scheduled(state))
            return state
        state = initial_state()
        state["scheduled"] = scheduled(state)
        self.write(key, state)
        return state

    def write(self, key, state):
        self.connection.execute(
            "INSERT OR REPLACE INTO workspaces VALUES (?, ?)",
            (key, json.dumps(state, allow_nan=False)),
        )
        self.connection.commit()


class Handler(BaseHTTPRequestHandler):
    def add_shadow_diagnostics(self, result, shadow_inputs):
        """Call only after authoritative state is captured/persisted and unlocked."""
        provider = getattr(self.server, "shadow_provider", None)
        if provider is not None:
            result["ml_shadow"] = diagnostics(shadow_inputs, provider)
        return result

    def send(self, status, body, content_type="application/json", filename=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if getattr(self, "cookie_headers", None):
            for cookie_header in self.cookie_headers:
                self.send_header("Set-Cookie", cookie_header)
        elif getattr(self, "new_cookie", None):
            self.send_header(
                "Set-Cookie",
                f"rj_session={self.new_cookie}; Path=/; "
                "HttpOnly; SameSite=Strict; Max-Age=2592000",
            )
        if filename:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{filename}"'
            )
        self.end_headers()
        self.wfile.write(body)

    def is_secure(self) -> bool:
        """Determine whether cookies must use the Secure flag."""
        val = os.environ.get("SECURE_COOKIES", "").strip().lower()
        if val in {"true", "1", "yes"}:
            return True
        if val in {"false", "0", "no"}:
            return False
        return os.environ.get("APP_ENV", "development").strip().lower() == "production"

    def set_auth_cookie(self, session_token: str):
        """Set dedicated authentication cookie."""
        lifetime = getattr(self.server.auth_manager, "session_lifetime", 2592000)
        parts = [
            f"rj_auth={session_token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={lifetime}",
        ]
        if self.is_secure():
            parts.append("Secure")
        if not hasattr(self, "cookie_headers"):
            self.cookie_headers = []
        self.cookie_headers.append("; ".join(parts))

    def clear_auth_cookie(self):
        """Expire dedicated authentication cookie."""
        parts = [
            "rj_auth=",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            "Max-Age=0",
            "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
        ]
        if self.is_secure():
            parts.append("Secure")
        if not hasattr(self, "cookie_headers"):
            self.cookie_headers = []
        self.cookie_headers.append("; ".join(parts))

    def get_auth_token(self) -> str:
        """Extract auth token from rj_auth cookie."""
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            if "rj_auth" in cookie:
                return cookie["rj_auth"].value
        except Exception:
            pass
        return ""

    def get_authenticated_user(self):
        """Verify session token and return (sanitized_user, session_doc)."""
        token = self.get_auth_token()
        if not token:
            return None, None
        return self.server.auth_manager.verify_session(token)

    def require_authenticated_user(self):
        """Verify authentication for protected routes.

        Sends error response and returns (None, None) if unauthenticated.
        """
        health = self.server.auth_manager.check_health()
        if health["status"] != "ok":
            self.send(
                503,
                {
                    "error": (
                        "Authentication service is currently unavailable. "
                        "MongoDB connection could not be established."
                    ),
                    "code": "service_unavailable",
                },
            )
            return None, None

        user, session_doc = self.get_authenticated_user()
        if not user or not session_doc:
            self.send(
                401,
                {
                    "error": (
                        "Authentication required. "
                        "Please sign in to access your treasury workspace."
                    ),
                    "code": "unauthorized",
                },
            )
            return None, None

        return user, session_doc

    def client_ip(self) -> str:
        """Return loopback client IP address."""
        if hasattr(self, "client_address") and self.client_address:
            return self.client_address[0]
        return "127.0.0.1"

    def session(self):
        """Legacy workspace session key fallback."""
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            key = cookie["rj_session"].value if "rj_session" in cookie else ""
        except Exception:
            key = ""
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            key = secrets.token_hex(32)
            self.new_cookie = key
        return key

    def allowed_host(self):
        return self.headers.get("Host") in {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }

    def do_GET(self):
        if not self.allowed_host():
            return self.send(403, {"error": "Loopback host required."})
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                db_health = self.server.auth_manager.check_health()
                status_code = 200 if db_health["status"] == "ok" else 503
                return self.send(
                    status_code,
                    {
                        "status": db_health["status"],
                        "mode": "simulation",
                        "database": db_health["database"],
                    },
                )

            if path == "/api/auth/me":
                db_health = self.server.auth_manager.check_health()
                if db_health["status"] != "ok":
                    return self.send(
                        503,
                        {
                            "error": "Authentication service is currently unavailable.",
                            "code": "service_unavailable",
                        },
                    )
                user, session_doc = self.get_authenticated_user()
                if not user or not session_doc:
                    return self.send(
                        401,
                        {
                            "authenticated": False,
                            "error": "Not authenticated.",
                            "code": "unauthorized",
                        },
                    )
                return self.send(
                    200,
                    {
                        "authenticated": True,
                        "user": user,
                        "csrf_token": session_doc.get("csrf_token", ""),
                    },
                )

            if path == "/api/template":
                records = sample_history()
                filename = "reserve-juggler-hourly-sample.csv"
                output = io.StringIO(newline="")
                writer = csv.DictWriter(output, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
                return self.send(
                    200, output.getvalue(), "text/csv; charset=utf-8", filename
                )

            if path in {"/api/state", "/api/export"}:
                user, _ = self.require_authenticated_user()
                if not user:
                    return
                workspace_key = f"user:{user['id']}"

                with self.server.store.lock:
                    state = self.server.store.read(workspace_key)
                    snap = snapshot(state)
                    shadow_inputs = capture_inputs(state)
                if path == "/api/state":
                    self.add_shadow_diagnostics(snap, shadow_inputs)
                    return self.send(200, snap)
                if path == "/api/export":
                    records = [
                        {
                            **r,
                            "source": snap["source"],
                            "currency": "INR",
                            "timestamp_ist": moment(r["timestamp"])
                            .astimezone(timezone(timedelta(hours=5, minutes=30)))
                            .isoformat(),
                            "model": snap["model"],
                            "confidence": snap["policy"]["confidence"],
                            "minimum_buffer": snap["policy"]["minimum_buffer"],
                            "withdrawal_stress_pct": snap["policy"][
                                "withdrawal_stress"
                            ],
                            "lock_hours": snap["policy"]["lock_hours"],
                            "recommended_sweep": snap["plan"]["sweep"],
                        }
                        for r in snap["forecast"]
                    ]
                    filename = "reserve-juggler-forecast.csv"
                    output = io.StringIO(newline="")
                    writer = csv.DictWriter(output, fieldnames=list(records[0]))
                    writer.writeheader()
                    writer.writerows(records)
                    return self.send(
                        200, output.getvalue(), "text/csv; charset=utf-8", filename
                    )

            static = {
                "/": "index.html",
                "/index.html": "index.html",
                "/styles.css": "styles.css",
                "/app.js": "app.js",
                "/planning.js": "planning.js",
                "/favicon.svg": "favicon.svg",
            }
            # The active frontend is React. Serve its production build when present.
            build = ROOT / "web" / "dist"
            if path in {"/", "/index.html"} and (build / "index.html").is_file():
                return self.send(
                    200, (build / "index.html").read_bytes(), "text/html; charset=utf-8"
                )
            if path.startswith("/assets/"):
                asset = (build / path.lstrip("/")).resolve()
                if (
                    not asset.is_relative_to((build / "assets").resolve())
                    or not asset.is_file()
                ):
                    return self.send(404, {"error": "Not found."})
                mime = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                return self.send(200, asset.read_bytes(), mime)
            if path not in static:
                return self.send(404, {"error": "Not found."})
            file = ROOT / "web" / static[path]
            mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self.send(200, file.read_bytes(), mime + "; charset=utf-8")
        except (ValueError, TypeError) as error:
            self.send(400, {"error": str(error)})
        except Exception:
            logging.exception("Request failed")
            self.send(500, {"error": "Unable to complete request. See the server log."})

    def do_POST(self):
        if not self.allowed_host():
            return self.send(403, {"error": "Loopback host required."})
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or parsed.hostname not in {
                "127.0.0.1",
                "localhost",
            }:
                return self.send(403, {"error": "Cross-origin requests are disabled."})
        path = urlparse(self.path).path
        content_type = self.headers.get("Content-Type", "").split(";")[0]
        if (
            path != "/api/auth/logout" or content_type
        ) and content_type != "application/json":
            return self.send(415, {"error": "Use application/json."})
        if (
            path == "/api/assistant"
            and origin
            and origin != "http://" + self.headers.get("Host", "")
        ):
            return self.send(403, {"error": "Chat requires a same-origin request."})

        valid_endpoints = {
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/sweep",
            "/api/advance",
            "/api/policy",
            "/api/import",
            "/api/reset",
            "/api/scenario",
            "/api/planning_policy",
            "/api/planning_balance",
            "/api/planning_event",
            "/api/planning_invest",
            "/api/planning_optimize",
            "/api/backtest",
            "/api/planning_scenario",
            "/api/assistant",
        }
        if path not in valid_endpoints:
            return self.send(404, {"error": "Unknown endpoint."})

        try:
            size = int(self.headers.get("Content-Length", "0"))
            limit = 100_000 if path == "/api/assistant" else 1_100_000
            if path == "/api/auth/logout" and size == 0:
                payload = {}
            else:
                if not 0 < size <= limit:
                    return self.send(
                        413, {"error": f"Request must be at most {limit} bytes."}
                    )
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Request must be a JSON object.")

            # Authentication Endpoints
            if path == "/api/auth/register":
                try:
                    user, token, csrf = self.server.auth_manager.register(
                        full_name=payload.get("full_name", ""),
                        email=payload.get("email", ""),
                        organization_name=payload.get("organization_name", ""),
                        job_title=payload.get("job_title"),
                        password=payload.get("password", ""),
                        confirm_password=payload.get("confirm_password"),
                    )
                    self.set_auth_cookie(token)
                    return self.send(201, {"user": user, "csrf_token": csrf})
                except AuthError as error:
                    return self.send(
                        error.status, {"error": error.message, "code": error.code}
                    )

            if path == "/api/auth/login":
                try:
                    user, token, csrf = self.server.auth_manager.login(
                        email=payload.get("email", ""),
                        password=payload.get("password", ""),
                        client_ip=self.client_ip(),
                    )
                    self.set_auth_cookie(token)
                    return self.send(200, {"user": user, "csrf_token": csrf})
                except AuthError as error:
                    return self.send(
                        error.status, {"error": error.message, "code": error.code}
                    )

            if path == "/api/auth/logout":
                token = self.get_auth_token()
                if token:
                    self.server.auth_manager.revoke_session(token)
                self.clear_auth_cookie()
                return self.send(
                    200, {"status": "ok", "message": "Logged out successfully."}
                )

            # All remaining endpoints are protected workspace APIs
            user, session_doc = self.require_authenticated_user()
            if not user or not session_doc:
                return

            # CSRF Protection: If X-CSRF-Token is passed, verify against session
            csrf_header = self.headers.get("X-CSRF-Token")
            if csrf_header and csrf_header != session_doc.get("csrf_token"):
                return self.send(
                    403, {"error": "Invalid CSRF token.", "code": "csrf_invalid"}
                )

            workspace_key = f"user:{user['id']}"

            if path == "/api/assistant":
                validate_request(payload)
                if not ASSISTANT_SLOTS.acquire(blocking=False):
                    return self.send(
                        429,
                        {
                            "error": "Treasury Assistant is busy. Please retry.",
                            "code": "busy",
                        },
                    )
                try:
                    with self.server.store.lock:
                        state = self.server.store.read(workspace_key)
                        try:
                            context = decision_context(snapshot(state))
                        except (ValueError, TypeError, KeyError, ArithmeticError):
                            context = {"available": False}
                    return self.send(200, answer(payload, context))
                finally:
                    ASSISTANT_SLOTS.release()

            with self.server.store.lock:
                state = self.server.store.read(workspace_key)
                if path == "/api/backtest":
                    from liquidity_forecasting.strategy_evaluation import (
                        compare_strategies,
                    )

                    report = compare_strategies(state["history"], hours=24)
                    report["source"] = state["source"]
                    return self.send(200, report)
                if path == "/api/planning_scenario":
                    stress = payload.get("stress", {})
                    if not isinstance(stress, dict):
                        raise ValueError("Stress must be an object.")
                    return self.send(
                        200,
                        {
                            "baseline": analyze(state),
                            "stressed": analyze(state, stress),
                        },
                    )
                if path == "/api/scenario":
                    policy = validate_policy(payload.get("policy"))
                    proposed = dict(state, policy=policy)
                    snap = snapshot(proposed)
                    return self.send(
                        200,
                        {
                            "plan": reserve_plan(
                                state["cash"], snap["forecast"], policy
                            ),
                            "forecast": snap["forecast"],
                            "policy": policy,
                        },
                    )
                updated = apply_action(state, path.removeprefix("/api/"), payload)
                result = snapshot(updated)
                shadow_inputs = capture_inputs(updated)
                self.server.store.write(workspace_key, updated)
            self.add_shadow_diagnostics(result, shadow_inputs)
            self.send(200, result)
        except AssistantError as error:
            self.send(error.status, {"error": str(error), "code": error.code})
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self.send(400, {"error": str(error)})
        except Exception:
            logging.exception("Action failed")
            self.send(
                500, {"error": "Action failed; no changes saved. See server log."}
            )


def create_server(port=8000, database=None, auth_manager=None, shadow_provider=None):
    load_env_file()
    if database is None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        database = ROOT / ".runtime" / "treasury.sqlite3"
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.store = Store(database)
    server.auth_manager = auth_manager or AuthManager()
    server.shadow_provider = shadow_provider
    return server


if __name__ == "__main__":
    load_env_file()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.port)
    db_status = (
        "MongoDB connected"
        if server.auth_manager.is_connected
        else "MongoDB unavailable"
    )
    print(
        f"Reserve Juggler · http://127.0.0.1:{server.server_port} · "
        f"{db_status} · simulation",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
