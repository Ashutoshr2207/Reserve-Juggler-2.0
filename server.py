"""Loopback-only web application. Run: python server.py --port 8000."""

import argparse
import csv
import io
import json
import logging
import mimetypes
import secrets
import sqlite3
import threading
from datetime import timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

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
        if getattr(self, "new_cookie", None):
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

    def session(self):
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
                return self.send(200, {"status": "ok", "mode": "simulation"})
            if path in {"/api/state", "/api/export", "/api/template"}:
                with self.server.store.lock:
                    state = self.server.store.read(self.session())
                    if path == "/api/state":
                        return self.send(200, snapshot(state))
                    if path == "/api/template":
                        records = sample_history()
                        filename = "reserve-juggler-hourly-sample.csv"
                    else:
                        snap = snapshot(state)
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
        if origin and origin != "http://" + self.headers.get("Host", ""):
            return self.send(403, {"error": "Cross-origin requests are disabled."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send(415, {"error": "Use application/json."})
        path = urlparse(self.path).path
        if path not in {
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
        }:
            return self.send(404, {"error": "Unknown endpoint."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1_100_000:
                return self.send(413, {"error": "Request must be smaller than 1.1 MB."})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Request must be a JSON object.")
            with self.server.store.lock:
                key = self.session()
                state = self.server.store.read(key)
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
                self.server.store.write(key, updated)
                self.send(200, result)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self.send(400, {"error": str(error)})
        except Exception:
            logging.exception("Action failed")
            self.send(
                500, {"error": "Action failed; no changes saved. See server log."}
            )


def create_server(port=8000, database=None):
    if database is None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        database = ROOT / ".runtime" / "treasury.sqlite3"
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.store = Store(database)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.port)
    print(
        f"Reserve Juggler · http://127.0.0.1:{server.server_port} · simulation",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
