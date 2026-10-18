"""Tests for Secure Banker Authentication and MongoDB User Management."""

import http.client
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from liquidity_forecasting.auth import (
    AuthManager,
    hash_token,
    normalize_email,
)
from server import create_server


def request(server, method, path, payload=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    body = json.dumps(payload) if payload is not None else None
    connection.request(method, path, body, headers or {})
    response = connection.getresponse()
    status, response_headers, data = (
        response.status,
        dict(response.getheaders()),
        response.read(),
    )
    connection.close()
    return status, response_headers, data


@pytest.fixture
def auth_server(tmp_path):
    test_db_name = f"test_rj_{uuid.uuid4().hex[:12]}"
    auth_manager = AuthManager(db_name=test_db_name)
    instance = create_server(
        0, tmp_path / "auth_test.sqlite3", auth_manager=auth_manager
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    instance.store.connection.close()
    if auth_manager._db is not None:
        try:
            auth_manager._db.users.drop()
            auth_manager._db.auth_sessions.drop()
        except Exception:
            pass
    auth_manager.close()


def test_registration_success(auth_server):
    payload = {
        "full_name": "Priya Sharma",
        "email": "priya.sharma@reservebank.example.com",
        "organization_name": "Reserve Bank of India",
        "job_title": "Chief Treasury Officer",
        "password": "SecurePassphrase2026!",
        "confirm_password": "SecurePassphrase2026!",
    }
    status, headers, body = request(
        auth_server,
        "POST",
        "/api/auth/register",
        payload,
        {"Content-Type": "application/json"},
    )
    assert status == 201
    data = json.loads(body)
    assert "user" in data
    user = data["user"]
    assert user["full_name"] == "Priya Sharma"
    assert user["email"] == "priya.sharma@reservebank.example.com"
    assert user["role"] == "banker"  # Self-registration automatically assigns banker
    assert user["account_status"] == "active"
    assert "password_hash" not in user  # Never return password hash
    assert "password" not in user
    assert "csrf_token" in data

    # Verify cookie was set
    set_cookie = headers.get("Set-Cookie", "")
    assert "rj_auth=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


def test_registration_duplicate_email(auth_server):
    payload = {
        "full_name": "Ananya Roy",
        "email": "ananya.roy@bank.example.com",
        "organization_name": "First Treasury Bank",
        "password": "ValidPassphrase123!",
    }
    status1, _, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        payload,
        {"Content-Type": "application/json"},
    )
    assert status1 == 201

    # Attempt duplicate with different casing
    duplicate_payload = dict(payload, email="ANANYA.ROY@BANK.EXAMPLE.COM")
    status2, _, body = request(
        auth_server,
        "POST",
        "/api/auth/register",
        duplicate_payload,
        {"Content-Type": "application/json"},
    )
    assert status2 == 400
    err = json.loads(body)
    assert "already exists" in err["error"].lower()


def test_registration_validation_errors(auth_server):
    # Short password (<12 chars)
    bad_pwd = {
        "full_name": "Test User",
        "email": "user@example.com",
        "organization_name": "Org",
        "password": "short",
    }
    status, _, body = request(
        auth_server,
        "POST",
        "/api/auth/register",
        bad_pwd,
        {"Content-Type": "application/json"},
    )
    assert status == 400
    assert "at least 12 characters" in json.loads(body)["error"]

    # Password mismatch
    mismatch = {
        "full_name": "Test User",
        "email": "user@example.com",
        "organization_name": "Org",
        "password": "ValidPassphrase123!",
        "confirm_password": "DifferentPassphrase123!",
    }
    status, _, body = request(
        auth_server,
        "POST",
        "/api/auth/register",
        mismatch,
        {"Content-Type": "application/json"},
    )
    assert status == 400
    assert "confirmation does not match" in json.loads(body)["error"]

    # Invalid email
    bad_email = {
        "full_name": "Test User",
        "email": "not-an-email",
        "organization_name": "Org",
        "password": "ValidPassphrase123!",
    }
    status, _, body = request(
        auth_server,
        "POST",
        "/api/auth/register",
        bad_email,
        {"Content-Type": "application/json"},
    )
    assert status == 400
    assert "valid work email" in json.loads(body)["error"].lower()


def test_login_success_and_me_endpoint(auth_server):
    # Register first
    request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Vikram Patel",
            "email": "vikram@treasury.example.com",
            "organization_name": "Gujarat State Co-op",
            "password": "VikramSecretPassphrase1!",
        },
        {"Content-Type": "application/json"},
    )

    # Login
    status, headers, body = request(
        auth_server,
        "POST",
        "/api/auth/login",
        {
            "email": "vikram@treasury.example.com",
            "password": "VikramSecretPassphrase1!",
        },
        {"Content-Type": "application/json"},
    )
    assert status == 200
    data = json.loads(body)
    assert data["user"]["full_name"] == "Vikram Patel"
    assert "password_hash" not in data["user"]
    auth_cookie = headers["Set-Cookie"].split(";")[0]

    # Verify GET /api/auth/me with cookie
    me_status, _, me_body = request(
        auth_server, "GET", "/api/auth/me", headers={"Cookie": auth_cookie}
    )
    assert me_status == 200
    me_data = json.loads(me_body)
    assert me_data["authenticated"] is True
    assert me_data["user"]["email"] == "vikram@treasury.example.com"
    assert "csrf_token" in me_data


def test_login_wrong_password_and_generic_errors(auth_server):
    # Register user
    request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Rohit Verma",
            "email": "rohit@bank.example.com",
            "organization_name": "Metro Bank",
            "password": "CorrectPassword123!",
        },
        {"Content-Type": "application/json"},
    )

    # Wrong password
    status1, _, body1 = request(
        auth_server,
        "POST",
        "/api/auth/login",
        {"email": "rohit@bank.example.com", "password": "WrongPassword999!"},
        {"Content-Type": "application/json"},
    )
    assert status1 == 401
    err1 = json.loads(body1)
    assert err1["error"] == "Invalid email or password."

    # Non-existent email: must return IDENTICAL generic error message
    # to prevent email enumeration
    status2, _, body2 = request(
        auth_server,
        "POST",
        "/api/auth/login",
        {"email": "nonexistent@bank.example.com", "password": "WrongPassword999!"},
        {"Content-Type": "application/json"},
    )
    assert status2 == 401
    err2 = json.loads(body2)
    assert err2["error"] == "Invalid email or password."


def test_login_rate_limiting(auth_server):
    rate_email = "ratelimit.test@bank.example.com"
    for _ in range(5):
        status, _, _ = request(
            auth_server,
            "POST",
            "/api/auth/login",
            {"email": rate_email, "password": "WrongPassword!"},
            {"Content-Type": "application/json"},
        )
        assert status == 401

    # 6th attempt should be rate limited (429)
    status, _, body = request(
        auth_server,
        "POST",
        "/api/auth/login",
        {"email": rate_email, "password": "WrongPassword!"},
        {"Content-Type": "application/json"},
    )
    assert status == 429
    assert "too many failed login attempts" in json.loads(body)["error"].lower()


def test_password_and_token_storage_security(auth_server):
    email = "security.audit@bank.example.com"
    pwd = "UltraSecurePassword2026!"
    status, headers, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Audit Officer",
            "email": email,
            "organization_name": "Security Org",
            "password": pwd,
        },
        {"Content-Type": "application/json"},
    )
    assert status == 201

    # Direct inspection of MongoDB
    db = auth_server.auth_manager._db
    user_doc = db.users.find_one({"normalized_email": normalize_email(email)})
    assert user_doc is not None
    # Verify password hash starts with Argon2id prefix
    assert user_doc["password_hash"].startswith("$argon2id$")
    assert pwd not in user_doc["password_hash"]

    # Verify session tokens in DB are SHA-256 hashes, not plaintext
    token = headers["Set-Cookie"].split(";")[0].removeprefix("rj_auth=")
    token_digest = hash_token(token)
    session_doc = db.auth_sessions.find_one({"token_hash": token_digest})
    assert session_doc is not None
    assert token not in str(session_doc)  # Raw token never stored in DB


def test_logout_and_revocation(auth_server):
    # Register and get session
    _, headers, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Logout Tester",
            "email": "logout@test.example.com",
            "organization_name": "Test Org",
            "password": "LogoutPassword123!",
        },
        {"Content-Type": "application/json"},
    )
    cookie = headers["Set-Cookie"].split(";")[0]

    # Verify me works
    assert (
        request(auth_server, "GET", "/api/auth/me", headers={"Cookie": cookie})[0]
        == 200
    )

    # Logout
    logout_status, logout_headers, _ = request(
        auth_server,
        "POST",
        "/api/auth/logout",
        {},
        {"Cookie": cookie, "Content-Type": "application/json"},
    )
    assert logout_status == 200
    assert "Max-Age=0" in logout_headers.get("Set-Cookie", "")

    # Attempt to access me with old revoked cookie
    revoked_status, _, _ = request(
        auth_server, "GET", "/api/auth/me", headers={"Cookie": cookie}
    )
    assert revoked_status == 401

    # Protected state endpoint also rejects revoked cookie
    state_status, _, _ = request(
        auth_server, "GET", "/api/state", headers={"Cookie": cookie}
    )
    assert state_status == 401


def test_session_expiration(auth_server):
    _, headers, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Expiring User",
            "email": "expiring@test.example.com",
            "organization_name": "Test Org",
            "password": "ExpiringPassword123!",
        },
        {"Content-Type": "application/json"},
    )
    cookie = headers["Set-Cookie"].split(";")[0]
    token = cookie.removeprefix("rj_auth=")
    token_digest = hash_token(token)

    # Manually backdate expiration in DB to simulate expired session
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    auth_server.auth_manager._db.auth_sessions.update_one(
        {"token_hash": token_digest},
        {"$set": {"expires_at": past}},
    )

    # Independent server-side check must immediately reject
    # without waiting for MongoDB TTL
    status, _, _ = request(auth_server, "GET", "/api/state", headers={"Cookie": cookie})
    assert status == 401


def test_unauthorized_direct_access_rejected(auth_server):
    # Direct access without cookie
    assert request(auth_server, "GET", "/api/state")[0] == 401
    assert request(auth_server, "GET", "/api/export")[0] == 401
    assert (
        request(
            auth_server,
            "POST",
            "/api/sweep",
            {"revision": 0},
            {"Content-Type": "application/json"},
        )[0]
        == 401
    )
    assert (
        request(
            auth_server,
            "POST",
            "/api/advance",
            {"revision": 0},
            {"Content-Type": "application/json"},
        )[0]
        == 401
    )


def test_cross_user_workspace_isolation(auth_server):
    # Register User A
    _, headers_a, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Banker Alpha",
            "email": "alpha@bank.example.com",
            "organization_name": "Alpha Bank",
            "password": "AlphaPassword123!",
        },
        {"Content-Type": "application/json"},
    )
    cookie_a = headers_a["Set-Cookie"].split(";")[0]

    # Register User B
    _, headers_b, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Banker Beta",
            "email": "beta@bank.example.com",
            "organization_name": "Beta Bank",
            "password": "BetaPassword123!",
        },
        {"Content-Type": "application/json"},
    )
    cookie_b = headers_b["Set-Cookie"].split(";")[0]

    # User A reads initial state
    raw_a = request(auth_server, "GET", "/api/state", headers={"Cookie": cookie_a})[2]
    state_a = json.loads(raw_a)
    assert state_a["revision"] == 0

    # User A sweeps
    sweep_status, _, sweep_raw = request(
        auth_server,
        "POST",
        "/api/sweep",
        {"revision": 0},
        {"Cookie": cookie_a, "Content-Type": "application/json"},
    )
    assert sweep_status == 200
    state_a_updated = json.loads(sweep_raw)
    assert state_a_updated["revision"] == 1
    assert len(state_a_updated["ledger"]) == 1

    # User B reads state - MUST be unaffected by User A's sweep!
    raw_b = request(auth_server, "GET", "/api/state", headers={"Cookie": cookie_b})[2]
    state_b = json.loads(raw_b)
    assert state_b["revision"] == 0
    assert len(state_b["ledger"]) == 0
    assert state_b["cash"] != state_a_updated["cash"]


def test_session_rotation_on_login(auth_server):
    # Register
    _, reg_headers, _ = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Rotate Tester",
            "email": "rotate@bank.example.com",
            "organization_name": "Rotate Bank",
            "password": "RotatePassword123!",
        },
        {"Content-Type": "application/json"},
    )
    reg_token = reg_headers["Set-Cookie"].split(";")[0].removeprefix("rj_auth=")

    # Login should rotate session and create a new token
    _, login_headers, _ = request(
        auth_server,
        "POST",
        "/api/auth/login",
        {"email": "rotate@bank.example.com", "password": "RotatePassword123!"},
        {"Content-Type": "application/json"},
    )
    login_token = login_headers["Set-Cookie"].split(";")[0].removeprefix("rj_auth=")
    assert reg_token != login_token


def test_csrf_protection(auth_server):
    _, headers, body = request(
        auth_server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "CSRF Tester",
            "email": "csrf@bank.example.com",
            "organization_name": "CSRF Bank",
            "password": "CSRFPassword123!",
        },
        {"Content-Type": "application/json"},
    )
    cookie = headers["Set-Cookie"].split(";")[0]
    valid_csrf = json.loads(body)["csrf_token"]

    # Wrong CSRF token should be rejected with 403
    status, _, _ = request(
        auth_server,
        "POST",
        "/api/sweep",
        {"revision": 0},
        {
            "Cookie": cookie,
            "Content-Type": "application/json",
            "X-CSRF-Token": "invalid_csrf_token_value",
        },
    )
    assert status == 403

    # Correct CSRF token should succeed
    status, _, _ = request(
        auth_server,
        "POST",
        "/api/sweep",
        {"revision": 0},
        {
            "Cookie": cookie,
            "Content-Type": "application/json",
            "X-CSRF-Token": valid_csrf,
        },
    )
    assert status == 200


def test_mongodb_unavailable_handling(tmp_path):
    # AuthManager with unreachable port
    bad_auth_manager = AuthManager(
        mongo_uri="mongodb://127.0.0.1:59999", db_name="unreachable"
    )
    unavail_server = create_server(
        0, tmp_path / "unavail.sqlite3", auth_manager=bad_auth_manager
    )
    thread = threading.Thread(target=unavail_server.serve_forever, daemon=True)
    thread.start()
    try:
        # Public homepage remains available
        home_status, _, home_body = request(unavail_server, "GET", "/")
        assert home_status == 200 and b"Reserve Juggler" in home_body

        # Health endpoint reports degraded status
        health_status, _, health_body = request(unavail_server, "GET", "/api/health")
        assert health_status == 503
        health_data = json.loads(health_body)
        assert health_data["status"] == "degraded"
        assert health_data["database"] == "unavailable"

        # Auth endpoints return 503 Service Unavailable
        reg_status, _, reg_body = request(
            unavail_server,
            "POST",
            "/api/auth/register",
            {
                "full_name": "Test",
                "email": "test@example.com",
                "organization_name": "Org",
                "password": "Password12345!",
            },
            {"Content-Type": "application/json"},
        )
        assert reg_status == 503
        assert "unavailable" in json.loads(reg_body)["error"].lower()

        # Protected state endpoint returns 503
        state_status, _, _ = request(unavail_server, "GET", "/api/state")
        assert state_status == 503
    finally:
        unavail_server.shutdown()
        unavail_server.server_close()
        unavail_server.store.connection.close()
        bad_auth_manager.close()
