import http.client
import json
import threading

import pytest

from server import Store, create_server


@pytest.fixture
def server(tmp_path, monkeypatch):
    import server as module

    monkeypatch.setattr(module, "snapshot", lambda state: state)
    instance = create_server(0, tmp_path / "test.sqlite3")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    instance.store.connection.close()


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


def test_static_health_and_traversal(server):
    assert request(server, "GET", "/api/health")[0] == 200
    status, headers, body = request(server, "GET", "/")
    assert status == 200 and b"Reserve Juggler" in body
    assert "Content-Security-Policy" in headers
    assert request(server, "GET", "/../server.py")[0] == 404


def test_session_isolation_and_persistence(server):
    _, headers, raw = request(server, "GET", "/api/state")
    cookie = headers["Set-Cookie"].split(";")[0]
    state = json.loads(raw)
    policy = dict(state["policy"], minimum_buffer=8_000_000)
    status, _, raw = request(
        server,
        "POST",
        "/api/policy",
        {"revision": 0, "policy": policy},
        {"Cookie": cookie, "Content-Type": "application/json"},
    )
    assert status == 200
    assert json.loads(raw)["policy"]["minimum_buffer"] == 8_000_000
    raw = request(server, "GET", "/api/state", headers={"Cookie": cookie})[2]
    assert json.loads(raw)["revision"] == 1
    raw = request(server, "GET", "/api/state")[2]
    assert json.loads(raw)["revision"] == 0


def test_origin_content_type_and_host_checks(server):
    assert request(server, "POST", "/api/reset", {"revision": 0})[0] == 415
    assert (
        request(
            server,
            "POST",
            "/api/reset",
            {"revision": 0},
            {"Content-Type": "application/json", "Origin": "https://example.com"},
        )[0]
        == 403
    )
    assert (
        request(server, "GET", "/api/state", headers={"Host": "example.com"})[0] == 403
    )


def test_invalid_action_does_not_modify_workspace(server):
    _, headers, _ = request(server, "GET", "/api/state")
    cookie = headers["Set-Cookie"].split(";")[0]
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
    _, response_headers, raw = request(server, "GET", "/api/state")
    state = json.loads(raw)
    headers = {
        "Cookie": response_headers["Set-Cookie"].split(";")[0],
        "Content-Type": "application/json",
    }
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
    instance = create_server(0, tmp_path / "integration.sqlite3")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        status, headers, raw = request(instance, "GET", "/api/state")
        assert status == 200
        original = json.loads(raw)
        cookie = headers["Set-Cookie"].split(";")[0]
        headers = {"Cookie": cookie, "Content-Type": "application/json"}
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


def test_optimized_failure_retry_backtest_and_stale_revision(server):
    _, response_headers, raw = request(server, "GET", "/api/state")
    original = json.loads(raw)
    headers = {
        "Cookie": response_headers["Set-Cookie"].split(";")[0],
        "Content-Type": "application/json",
    }
    payload = {"revision": 0, "execution": "timeout", "request_id": "timeout-demo"}
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
