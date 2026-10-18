"""Shadow integration cannot change treasury decisions; no MongoDB/data needed."""

import builtins
import copy
import importlib.util
import io
import json
import threading
import time
from email.message import Message
from types import SimpleNamespace

import pandas as pd
import pytest

from liquidity_forecasting import ml_shadow, treasury
from liquidity_forecasting.strategy_evaluation import evaluation_forecast
from server import Handler, Store


@pytest.fixture(autouse=True)
def isolated_shadow_executor(monkeypatch):
    # Production has one process-lifetime executor. Only tests replace it so a
    # deliberately opened circuit cannot contaminate unrelated test cases.
    if importlib.util.find_spec("reserve_juggler_ml") is not None:
        from reserve_juggler_ml.integration import shadow

        monkeypatch.setattr(shadow, "_EXECUTOR", shadow.ShadowExecutor())


@pytest.fixture
def state(monkeypatch):
    current = treasury.initial_state()
    monkeypatch.setattr(treasury, "forecast", lambda s: (
        evaluation_forecast(s["history"]), "Fixture seasonal fallback", False, 12.
    ))
    monkeypatch.delenv("RJ_ML_SHADOW_ENABLED", raising=False)
    return current


@pytest.fixture
def provider():
    pytest.importorskip("reserve_juggler_ml")
    from reserve_juggler_ml.forecasting.base import ForecastOutput
    from reserve_juggler_ml.integration.contract import FLOW_SCOPE, SEMANTICS, UNIT, ModelSpec

    instance = SimpleNamespace(
        spec=ModelSpec(
            model_id="SyntheticFixture", version="test-1", training_currency="INR",
            unit=UNIT, dataset_id="synthetic-fixture", dataset_sha256="0" * 64,
            configuration_id="fixture-1", trained_through="2026-09-01T00:00:00Z",
            interval_method="fixture-not-calibrated", timestamp_semantics=SEMANTICS,
            feature_timezone="UTC", flow_scope=FLOW_SCOPE,
        ), calls=0,
    )

    def predict(history, *, periods, alpha, frequency):
        instance.calls += 1
        instance.seen_history = history.copy(deep=True)
        index = pd.date_range(
            history.index[-1] + pd.DateOffset(hours=1), periods=periods, freq=frequency
        )
        return {
            target: ForecastOutput(
                pd.Series([value] * periods, index=index),
                pd.Series([value - 1] * periods, index=index),
                pd.Series([value + 1] * periods, index=index), instance.spec.model_id,
            )
            for target, value in (("deposits", 1e11), ("withdrawals", 10.))
        }

    instance.predict = predict
    return instance


def test_disabled_by_default_without_optional_package_import(state, monkeypatch):
    real_import = builtins.__import__

    def forbid(name, *args, **kwargs):
        assert not name.startswith("reserve_juggler_ml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid)
    result = treasury.snapshot(state)
    assert result["ml_shadow"]["status"] == "disabled"
    assert result["ml_shadow"]["enabled"] is False
    assert result["ml_shadow"]["controls_treasury"] is False
    assert result["model"] == "Fixture seasonal fallback"


def test_inr_usd_mismatch_skipped_before_import_or_artifact_access(state, monkeypatch):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    real_import = builtins.__import__

    def forbid(name, *args, **kwargs):
        assert not name.startswith("reserve_juggler_ml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid)
    result = ml_shadow.diagnostics(state)
    assert result["code"] == "CURRENCY_MISMATCH"
    assert result["status"] == "skipped"
    assert result["input_currency"] == "INR"
    assert result["model_currency"] == "USD"
    assert result["inference_ran"] is False


def test_missing_artifacts_never_trigger_training_or_loading(state, monkeypatch):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    result = ml_shadow.diagnostics(dict(state, currency="USD"))
    assert result["code"] == "MODEL_UNAVAILABLE"
    assert result["inference_ran"] is False


@pytest.mark.parametrize("currency", [None, "", "EUR"])
def test_missing_or_unknown_input_currency_not_assumed(state, monkeypatch, currency):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    assert ml_shadow.diagnostics(dict(state, currency=currency))["code"] == "UNSUPPORTED_CURRENCY"


def test_unavailable_package_retains_existing_forecast(state, provider, monkeypatch):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    real_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name.startswith("reserve_juggler_ml"):
            raise ModuleNotFoundError("optional package not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    result = treasury.snapshot(state, shadow_provider=provider)
    assert result["ml_shadow"]["code"] == "ML_PACKAGE_UNAVAILABLE"
    assert len(result["forecast"]) == 72
    assert provider.calls == 0


def test_success_is_advisory_and_uses_full_history(state, provider, monkeypatch):
    before = copy.deepcopy(state)
    baseline = treasury.snapshot(state)
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    result = treasury.snapshot(state, shadow_provider=provider)
    assert provider.calls == 1
    assert len(provider.seen_history) == 1008
    assert result["ml_shadow"]["code"] == "SHADOW_VALIDATED"
    assert result["ml_shadow"]["controls_treasury"] is False
    assert "predictions" not in result["ml_shadow"]
    assert result["currency"] == "INR"
    assert state == before
    assert {k: v for k, v in result.items() if k != "ml_shadow"} == {
        k: v for k, v in baseline.items() if k != "ml_shadow"
    }


@pytest.mark.parametrize("problem, code, ran", [
    ("exception", "INFERENCE_FAILED", True),
    ("timeout", "TIMEOUT", True),
    ("negative", "INVALID_NUMBER", True),
    ("metadata", "INVALID_MODEL_METADATA", False),
    ("currency", "CURRENCY_MISMATCH", False),
])
def test_failed_shadow_cannot_break_legacy(state, provider, monkeypatch, problem, code, ran):
    from dataclasses import replace

    baseline = treasury.snapshot(state)
    original = provider.predict

    def broken(*args, **kwargs):
        if problem == "exception":
            raise RuntimeError("private artifact path")
        if problem == "timeout":
            raise TimeoutError()
        result = original(*args, **kwargs)
        result["withdrawals"].mean.iloc[0] = -1
        return result

    if problem == "metadata":
        provider.spec = None
    elif problem == "currency":
        provider.spec = replace(provider.spec, training_currency="USD")
    else:
        provider.predict = broken
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    actual = treasury.snapshot(state, shadow_provider=provider)
    diagnostic = actual.pop("ml_shadow")
    baseline.pop("ml_shadow")
    assert actual == baseline
    assert diagnostic["code"] == code
    assert diagnostic["inference_ran"] is ran
    assert diagnostic["controls_treasury"] is False
    assert "private artifact path" not in json.dumps(diagnostic)


@pytest.mark.parametrize("action, payload", [
    ("sweep", {}), ("planning_optimize", {}), ("planning_invest", {}),
    ("advance", {}), ("planning_event", {"kind": "payment", "amount": 100, "hours": 0.25}),
    ("planning_optimize", {"execution": "failure"}),
])
def test_actions_identical_with_shadow_enabled(state, provider, monkeypatch, action, payload):
    baseline = treasury.apply_action(state, action, {"revision": 0, **payload})
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    treasury.snapshot(state, shadow_provider=provider)
    actual = treasury.apply_action(state, action, {"revision": 0, **payload})
    assert actual == baseline
    assert "ml_shadow" not in actual
    assert provider.calls == 1  # Actions never invoke or consult the provider.


def handler_for(state, provider, *, server=None):
    """Real handlers, authenticated fixture, in-memory SQLite; no network or MongoDB."""
    handler = object.__new__(Handler)
    handler.server = server or SimpleNamespace(
        server_port=8000, store=Store(":memory:"), shadow_provider=provider,
    )
    handler.headers = Message()
    handler.headers["Host"] = "127.0.0.1:8000"
    handler.require_authenticated_user = lambda: ({"id": "fixture"}, {"csrf_token": "test"})
    if server is None:
        handler.server.store.write("user:fixture", state)
    handler.send = lambda status, body, *args: setattr(handler, "response", (status, body, args))
    return handler


def test_real_get_post_state_and_csv_contracts(state, provider, monkeypatch):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    handler = handler_for(state, provider)
    try:
        handler.path = "/api/state"
        handler.do_GET()
        status, result, _ = handler.response
        assert status == 200
        assert result["ml_shadow"]["status"] == "completed"
        assert result["schema_version"] == 2
        assert len(result["forecast"]) == len(result["gross_forecast"]["rows"]) == 72
        assert set(result["forecast"][0]) == {
            "timestamp", "mean", "lower", "upper", "withdrawals",
            "balance", "lower_balance", "upper_balance",
        }
        json.dumps(result, allow_nan=False)
        handler.path = "/api/export"
        handler.do_GET()
        assert handler.response[0] == 200
        assert handler.response[1].splitlines()[0] == (
            "timestamp,mean,lower,upper,withdrawals,balance,lower_balance,upper_balance,"
            "source,currency,timestamp_ist,model,confidence,minimum_buffer,"
            "withdrawal_stress_pct,lock_hours,recommended_sweep"
        )
        handler.path = "/api/planning_optimize"
        body = json.dumps({"revision": 0}).encode()
        handler.headers["Content-Type"] = "application/json"
        handler.headers["Content-Length"] = str(len(body))
        handler.rfile = io.BytesIO(body)
        handler.do_POST()
        assert handler.response[0] == 200
        result = handler.response[1]
        assert result["ml_shadow"]["status"] == "completed"
        assert result["revision"] == 1
        expected = treasury.apply_action(state, "planning_optimize", {"revision": 0})
        assert handler.server.store.read("user:fixture") == expected
        assert "ml_shadow" not in handler.server.store.read("user:fixture")
    finally:
        handler.server.store.connection.close()


def test_invalid_configuration_visible_without_altering_legacy(state, monkeypatch):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "yes")
    result = treasury.snapshot(state)
    assert result["ml_shadow"]["code"] == "INVALID_CONFIGURATION"
    assert len(result["forecast"]) == 72


def test_broken_metadata_property_cannot_break_legacy(state, monkeypatch, caplog):
    pytest.importorskip("reserve_juggler_ml")

    class Broken:
        @property
        def spec(self):
            raise RuntimeError("private metadata path")

    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    result = treasury.snapshot(state, shadow_provider=Broken())
    assert result["ml_shadow"]["code"] == "INTEGRATION_FAILED"
    assert len(result["forecast"]) == 72
    assert "private metadata path" not in json.dumps(result["ml_shadow"])
    assert "private metadata path" not in caplog.text


def call_handler(handler, method, path, payload=None):
    handler.path = path
    if payload is not None:
        body = json.dumps(payload).encode()
        handler.headers["Content-Type"] = "application/json"
        handler.headers["Content-Length"] = str(len(body))
        handler.rfile = io.BytesIO(body)
    getattr(handler, "do_" + method)()
    assert handler.response[0] == 200
    return handler.response[1]


def financial_fields(response):
    return {k: v for k, v in response.items() if k != "ml_shadow"}


def test_deadline_releases_request_and_preserves_treasury_availability(
    state, provider, monkeypatch
):
    """Real default 2s deadline, live blocked worker, real handlers and SQLite."""
    from reserve_juggler_ml.integration import shadow

    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    entered, release, request_done = (
        threading.Event(), threading.Event(), threading.Event()
    )
    first = handler_for(state, provider)
    server = first.server
    original_predict = provider.predict
    started_calls = []
    worker_had_no_transaction_lock = []

    def blocked(history, **kwargs):
        started_calls.append(True)
        acquired = server.store.lock.acquire(blocking=False)
        worker_had_no_transaction_lock.append(acquired)
        if acquired:
            server.store.lock.release()
        assert set(history.columns) == {"deposits", "withdrawals"}
        entered.set()
        if not release.wait(6):
            raise TimeoutError("bounded regression cleanup")
        # Accidental mutation of the provider's own input cannot reach SQLite.
        history.iloc[0, 0] = 0
        return original_predict(history, **kwargs)

    provider.predict = blocked
    placement = {"revision": 0, "request_id": "blocked-placement"}
    expected_one = treasury.apply_action(state, "planning_optimize", placement)
    first_result = {}

    def first_request():
        try:
            first_result["response"] = call_handler(
                first, "POST", "/api/planning_optimize", placement
            )
        except BaseException as exc:
            first_result["error"] = exc
        finally:
            request_done.set()

    request_thread = threading.Thread(target=first_request, daemon=True)
    began = time.monotonic()
    try:
        request_thread.start()
        assert entered.wait(3), "Shadow provider did not start"
        assert worker_had_no_transaction_lock == [True]
        with server.store.lock:
            assert server.store.read("user:fixture") == expected_one

        read = handler_for(state, provider, server=server)
        read_began = time.monotonic()
        read_result = call_handler(read, "GET", "/api/state")
        assert time.monotonic() - read_began < 1
        assert read_result["ml_shadow"]["code"] == "SHADOW_BUSY"
        assert financial_fields(read_result) == financial_fields(
            treasury.snapshot(expected_one)
        )

        event_payload = {
            "revision": 1, "request_id": "second-mutation", "kind": "deposit",
            "amount": 100, "hours": 2,
        }
        second = handler_for(state, provider, server=server)
        second_result = call_handler(
            second, "POST", "/api/planning_event", event_payload
        )
        assert second_result["ml_shadow"]["code"] == "SHADOW_BUSY"
        expected_two = treasury.apply_action(
            expected_one, "planning_event", event_payload
        )
        with server.store.lock:
            assert server.store.read("user:fixture") == expected_two

        assert request_done.wait(3), "Request waited on the abandoned provider"
        assert time.monotonic() - began < 3.5
        assert "error" not in first_result
        timed_out = first_result["response"]
        assert timed_out["ml_shadow"]["code"] == "TIMEOUT"
        assert financial_fields(timed_out) == financial_fields(
            treasury.snapshot(expected_one)
        )
        worker = shadow._EXECUTOR._worker
        assert worker.daemon and worker.is_alive()

        # Circuit is shared across requests and providers, with no worker queue.
        for _ in range(5):
            followup = handler_for(state, provider, server=server)
            result = call_handler(followup, "GET", "/api/state")
            assert result["ml_shadow"]["code"] == "CIRCUIT_OPEN"
            assert shadow._EXECUTOR._worker is worker
        assert len(started_calls) == 1

        # Exact retry cannot duplicate the already committed investment.
        retry = handler_for(state, provider, server=server)
        retried = call_handler(retry, "POST", "/api/planning_optimize", placement)
        assert retried["revision"] == 2
        assert len(retried["tranches"]) == 1
        with server.store.lock:
            assert server.store.read("user:fixture") == expected_two
        assert not release.is_set()  # All checks completed with provider blocked.
    finally:
        release.set()
        request_thread.join(3)
        worker = shadow._EXECUTOR._worker
        if worker is not None:
            worker.join(3)
        server.store.connection.close()
    assert not request_thread.is_alive()
    assert not worker.is_alive()
    assert first_result["response"]["ml_shadow"]["code"] == "TIMEOUT"


def test_capture_inputs_has_no_financial_state_or_shared_history(state):
    captured = ml_shadow.capture_inputs(state)
    assert set(captured) == {"currency", "history", "policy"}
    assert captured["policy"] == {"confidence": 95}
    original = copy.deepcopy(state)
    captured["history"][0]["deposits"] = 0
    captured["policy"]["confidence"] = 90
    assert state == original


def test_mutation_is_committed_before_provider_exception(state, provider, monkeypatch):
    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    handler = handler_for(state, provider)

    def fail(history, **kwargs):
        # Reading this from the worker would deadlock if the request still held
        # the store lock. Use a bounded acquisition so a regression cannot hang.
        acquired = handler.server.store.lock.acquire(timeout=0.5)
        try:
            assert acquired
            assert handler.server.store.read("user:fixture")["revision"] == 1
        finally:
            if acquired:
                handler.server.store.lock.release()
        raise RuntimeError("private provider detail")

    provider.predict = fail
    try:
        result = call_handler(
            handler, "POST", "/api/planning_optimize", {"revision": 0}
        )
        assert result["ml_shadow"]["code"] == "INFERENCE_FAILED"
        assert result["revision"] == 1
        expected = treasury.apply_action(state, "planning_optimize", {"revision": 0})
        assert handler.server.store.read("user:fixture") == expected
        assert "private provider detail" not in json.dumps(result)
    finally:
        handler.server.store.connection.close()


@pytest.mark.parametrize("path", ["/api/export", "/api/scenario", "/api/assistant"])
def test_routes_without_shadow_output_never_call_provider(
    state, provider, monkeypatch, path
):
    import server as server_module

    monkeypatch.setenv("RJ_ML_SHADOW_ENABLED", "true")
    monkeypatch.setattr(server_module, "answer", lambda payload, context: {"reply": "fixture"})
    handler = handler_for(state, provider)
    try:
        if path == "/api/export":
            call_handler(handler, "GET", path)
        elif path == "/api/scenario":
            call_handler(handler, "POST", path, {"policy": state["policy"]})
        else:
            call_handler(handler, "POST", path, {"message": "How does this work?"})
        assert provider.calls == 0
    finally:
        handler.server.store.connection.close()
