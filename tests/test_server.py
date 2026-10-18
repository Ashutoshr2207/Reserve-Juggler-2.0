import http.client
import json
import threading
import uuid

import pytest

from liquidity_forecasting.auth import AuthManager
from server import Store, create_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    import server as module

    monkeypatch.setattr(module, "snapshot", lambda state: state)
    test_db_name = f"test_rj_srv_{uuid.uuid4().hex[:12]}"
    auth_manager = AuthManager(db_name=test_db_name)
    instance = create_server(0, tmp_path / "test.sqlite3", auth_manager=auth_manager)
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


def register_and_login(
    server, email="banker@example.com", password="SecurePassword123!"
):
    status, headers, body = request(
        server,
        "POST",
        "/api/auth/register",
        {
            "full_name": "Test Banker",
            "email": email,
            "organization_name": "Test Bank",
            "password": password,
        },
        {"Content-Type": "application/json"},
    )
    assert status == 201
    return headers["Set-Cookie"].split(";")[0]


def test_static_health_and_traversal(server):
    assert request(server, "GET", "/api/health")[0] == 200
    status, headers, body = request(server, "GET", "/")
    assert status == 200 and b"Reserve Juggler" in body
    assert "Content-Security-Policy" in headers
    assert request(server, "GET", "/../server.py")[0] == 404


def test_session_isolation_and_persistence(server):
    # Unauthenticated access is blocked
    assert request(server, "GET", "/api/state")[0] == 401

    cookie1 = register_and_login(server, "banker1@example.com")
    cookie2 = register_and_login(server, "banker2@example.com")

    _, _, raw1 = request(server, "GET", "/api/state", headers={"Cookie": cookie1})
    state = json.loads(raw1)
    policy = dict(state["policy"], minimum_buffer=8_000_000)
    status, _, raw = request(
        server,
        "POST",
        "/api/policy",
        {"revision": 0, "policy": policy},
        {"Cookie": cookie1, "Content-Type": "application/json"},
    )
    assert status == 200
    assert json.loads(raw)["policy"]["minimum_buffer"] == 8_000_000

    # Banker 1 sees updated revision
    raw = request(server, "GET", "/api/state", headers={"Cookie": cookie1})[2]
    assert json.loads(raw)["revision"] == 1

    # Banker 2 has isolated workspace at revision 0
    raw = request(server, "GET", "/api/state", headers={"Cookie": cookie2})[2]
    assert json.loads(raw)["revision"] == 0


def test_origin_content_type_and_host_checks(server):
    assert request(server, "POST", "/api/reset", {"revision": 0})[0] == 415
    cookie = register_and_login(server, "origin_check@example.com")
    assert (
        request(
            server,
            "POST",
            "/api/reset",
            {"revision": 0},
            {
                "Content-Type": "application/json",
                "Origin": "https://example.com",
                "Cookie": cookie,
            },
        )[0]
        == 403
    )
    assert (
        request(
            server,
            "POST",
            "/api/reset",
            {"revision": 0},
            {
                "Content-Type": "application/json",
                "Origin": "http://localhost:5173",
                "Cookie": cookie,
            },
        )[0]
        == 200
    )
    assert (
        request(
            server,
            "GET",
            "/api/state",
            headers={"Host": "example.com", "Cookie": cookie},
        )[0]
        == 403
    )


def test_invalid_action_does_not_modify_workspace(server):
    cookie = register_and_login(server, "invalid_action@example.com")
    status, _, _ = request(
        server,
        "POST",
        "/api/policy",
        {"revision": 0, "policy": {}},
        {"Cookie": cookie, "Content-Type": "application/json"},
    )
    assert status == 400
    assert (
        json.loads(request(server, "GET", "/api/state", headers={"Cookie": cookie})[2])[
            "revision"
        ]
        == 0
    )


def test_store_survives_reopening(tmp_path):
    path = tmp_path / "persistent.sqlite3"
    store = Store(path)
    state = store.read("example")
    state["cash"] = 123
    store.write("example", state)
    store.connection.close()
    reopened = Store(path)
    assert reopened.read("example")["cash"] == 123
    reopened.connection.close()


def test_planning_api_events_stress_and_investment(server):
    cookie = register_and_login(server, "planning_events@example.com")
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/json",
    }
    _, _, raw = request(server, "GET", "/api/state", headers=headers)
    state = json.loads(raw)
    status, _, raw = request(
        server,
        "POST",
        "/api/planning_scenario",
        {"stress": {"withdrawals": 50, "delay": 12}},
        headers,
    )
    assert status == 200
    compared = json.loads(raw)
    assert compared["stressed"]["selected"]["suggested"] == 0
    assert compared["baseline"]["selected"]["suggested"] > 0
    status, _, raw = request(
        server,
        "POST",
        "/api/planning_event",
        {
            "revision": state["revision"],
            "kind": "payment",
            "amount": 500_000_000,
            "hours": 2,
        },
        headers,
    )
    assert status == 200
    changed = json.loads(raw)
    assert changed["decisions"][0]["after"]["suggested"] == 0
    assert changed["decisions"][0]["after"]["shortfall"] > 0
    assert (
        request(
            server,
            "POST",
            "/api/planning_invest",
            {"revision": changed["revision"]},
            headers,
        )[0]
        == 400
    )
    current = json.loads(request(server, "GET", "/api/state", headers=headers)[2])
    assert current["cash"] == state["cash"]
    assert current["revision"] == changed["revision"]


def test_complete_http_workflow_with_real_model(tmp_path):
    """Exercise the actual API contract, model, ledger, and exported values."""
    test_db_name = f"test_rj_workflow_{uuid.uuid4().hex[:12]}"
    auth_manager = AuthManager(db_name=test_db_name)
    instance = create_server(
        0, tmp_path / "integration.sqlite3", auth_manager=auth_manager
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        cookie = register_and_login(instance, "full_workflow@example.com")
        headers = {"Cookie": cookie, "Content-Type": "application/json"}
        status, _, raw = request(instance, "GET", "/api/state", headers=headers)
        assert status == 200
        original = json.loads(raw)
        assert original["model"] in ("SARIMAX", "Seasonal Naive (fallback)")
        assert original["plan"]["sweep"] > 0
        policy = dict(original["policy"], withdrawal_stress=35)
        status, _, raw = request(
            instance, "POST", "/api/scenario", {"policy": policy}, headers
        )
        assert status == 200
        stressed = json.loads(raw)
        assert stressed["plan"]["shortfall"] > 0
        assert stressed["plan"]["sweep"] == 0
        status, _, raw = request(
            instance, "POST", "/api/sweep", {"revision": 0}, headers
        )
        assert status == 200
        swept = json.loads(raw)
        assert swept["cash"] + swept["vault"] == 350_000_000
        assert swept["policy"]["withdrawal_stress"] == 0
        assert swept["ledger"][0]["type"] == "Sweep"
        assert (
            request(instance, "POST", "/api/sweep", {"revision": 0}, headers)[0] == 400
        )
        status, _, raw = request(
            instance, "POST", "/api/advance", {"revision": 1}, headers
        )
        assert status == 200
        advanced = json.loads(raw)
        assert advanced["as_of"] > swept["as_of"]
        assert advanced["tranches"] == swept["tranches"]
        status, export_headers, raw = request(
            instance, "GET", "/api/export", headers=headers
        )
        assert status == 200
        assert "text/csv" in export_headers["Content-Type"]
        assert b"recommended_sweep" in raw and b"withdrawal_stress_pct" in raw
        assert len(raw.decode().splitlines()) == 73
        status, _, raw = request(
            instance, "POST", "/api/reset", {"revision": 2}, headers
        )
        assert status == 200
        reset = json.loads(raw)
        assert reset["revision"] == 3 and reset["ledger"] == []
        assert reset["cash"] == 100_000_000
        _, _, csv = request(instance, "GET", "/api/template", headers=headers)
        status, _, raw = request(
            instance,
            "POST",
            "/api/import",
            {"revision": 3, "csv": csv.decode()},
            headers,
        )
        assert status == 200
        assert json.loads(raw)["source"] == "Imported cashflows · simulated balances"
    finally:
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


def test_optimized_failure_retry_backtest_and_stale_revision(server):
    cookie = register_and_login(server, "retry_backtest@example.com")
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/json",
    }
    _, _, raw = request(server, "GET", "/api/state", headers=headers)
    original = json.loads(raw)
    payload = {
        "revision": 0,
        "execution": "timeout",
        "request_id": "timeout-demo",
    }
    status, _, raw = request(server, "POST", "/api/planning_optimize", payload, headers)
    assert status == 200
    failed = json.loads(raw)
    assert failed["cash"] == original["cash"] and failed["tranches"] == []
    status, _, raw = request(server, "POST", "/api/planning_optimize", payload, headers)
    assert status == 200 and json.loads(raw) == failed
    assert (
        request(
            server,
            "POST",
            "/api/planning_optimize",
            {"revision": 0, "request_id": "stale"},
            headers,
        )[0]
        == 400
    )
    status, _, raw = request(server, "POST", "/api/backtest", {}, headers)
    assert status == 200 and len(json.loads(raw)["results"]) == 3
    status, _, raw = request(server, "GET", "/api/state", headers=headers)
    assert status == 200 and json.loads(raw) == failed
