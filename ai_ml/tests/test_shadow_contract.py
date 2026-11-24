"""Synthetic boundary fixtures only: no committee data, artifacts or training."""

import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from reserve_juggler_ml.forecasting.base import ForecastOutput
from reserve_juggler_ml.integration.adapter import adapt_to_backend_state
from reserve_juggler_ml.integration.contract import (
    FLOW_SCOPE,
    SEMANTICS,
    UNIT,
    IntegrationError,
    ModelSpec,
    ShadowRequest,
)
from reserve_juggler_ml.integration.shadow import infer_shadow
from reserve_juggler_ml.integration import shadow


@pytest.fixture(autouse=True)
def isolated_shadow_executor(monkeypatch):
    monkeypatch.setattr(shadow, "_EXECUTOR", shadow.ShadowExecutor())


@pytest.fixture
def request_data():
    times = pd.date_range("2026-10-01T00:00:00+05:30", periods=336, freq="h")
    history = [
        {"timestamp": t.isoformat(), "deposits": 1000.0, "withdrawals": 800.0}
        for t in times
    ]
    return ShadowRequest("INR", history[-1]["timestamp"], history, 0.95)


class FixtureProvider:
    """Already-loaded stand-in; produces controlled, deliberately large forecasts."""

    def __init__(self, **overrides):
        self.spec = ModelSpec(
            model_id="SyntheticFixture", version="test-1", training_currency="INR",
            unit=UNIT, dataset_id="synthetic-fixture-no-real-training",
            dataset_sha256="0" * 64, configuration_id="constant-fixture-1",
            trained_through="2026-09-01T00:00:00Z",
            interval_method="fixture-bands-not-calibrated",
            timestamp_semantics=SEMANTICS, feature_timezone="UTC",
        )
        self.spec = replace(self.spec, **overrides)
        self.calls = 0
        self.history = None

    def predict(self, history, *, periods, alpha, frequency):
        self.calls += 1
        self.history = history.copy(deep=True)
        assert periods == 72 and alpha == 0.05 and frequency == "h"
        index = pd.date_range(
            history.index[-1] + pd.DateOffset(hours=1), periods=72, freq="h"
        )
        return {
            target: ForecastOutput(
                pd.Series([value] * 72, index=index),
                pd.Series([value - 10] * 72, index=index),
                pd.Series([value + 10] * 72, index=index), self.spec.model_id,
            )
            for target, value in (("deposits", 10000.), ("withdrawals", 100.))
        }


def test_aligned_inference_round_trip_and_causal_cutoff(request_data):
    provider = FixtureProvider()
    output = infer_shadow(request_data, provider)
    assert provider.calls == 1
    assert len(provider.history) == 336
    assert set(provider.history.columns) == {"deposits", "withdrawals"}
    assert provider.history.index[-1] == pd.Timestamp(request_data.as_of)
    assert provider.history.index.max() < pd.Timestamp(output.response.predictions[0].timestamp)
    assert output.response.predictions[0].timestamp == "2026-10-14T18:30:00Z"
    assert output.response.model_metadata.training_cutoff == provider.spec.trained_through
    assert output.net_rows[0]["mean"] == 9900
    assert len(output.gross_forecast["rows"]) == 72
    assert "UNCALIBRATED" in output.response.warnings[0]
    assert not output.response.liquidity_risk


@pytest.mark.parametrize("currency", [None, "", "EUR", "inr"])
def test_explicit_currency_required(request_data, currency):
    provider = FixtureProvider()
    with pytest.raises(IntegrationError, match="currency"):
        infer_shadow(replace(request_data, currency=currency), provider)
    assert provider.calls == 0


@pytest.mark.parametrize("changes, code", [
    ({"training_currency": "USD"}, "CURRENCY_MISMATCH"),
    ({"training_currency": None}, "UNSUPPORTED_CURRENCY"),
    ({"version": ""}, "INVALID_MODEL_METADATA"),
    ({"dataset_sha256": ""}, "INVALID_MODEL_METADATA"),
    ({"dataset_id": ""}, "INVALID_MODEL_METADATA"),
    ({"configuration_id": ""}, "INVALID_MODEL_METADATA"),
    ({"interval_method": ""}, "INVALID_MODEL_METADATA"),
    ({"timestamp_semantics": "interval_start"}, "UNSUPPORTED_CONTRACT"),
    ({"feature_timezone": "Asia/Kolkata"}, "UNSUPPORTED_CONTRACT"),
    ({"unit": "paise"}, "UNSUPPORTED_CONTRACT"),
    ({"horizon_hours": 48}, "UNSUPPORTED_CONTRACT"),
    ({"min_history_hours": 500}, "INSUFFICIENT_HISTORY"),
    ({"trained_through": "2026-10-31T00:00:00Z"}, "FUTURE_TRAINING_DATA"),
])
def test_model_gates_before_inference(request_data, changes, code):
    provider = FixtureProvider(**changes)
    with pytest.raises(IntegrationError) as error:
        infer_shadow(request_data, provider)
    assert error.value.code == code
    assert error.value.inference_ran is False
    assert provider.calls == 0


def test_missing_provider_and_metadata(request_data):
    for provider in (None, object()):
        with pytest.raises(IntegrationError) as error:
            infer_shadow(request_data, provider)
        assert error.value.code in {"MODEL_UNAVAILABLE", "INVALID_MODEL_METADATA"}


@pytest.mark.parametrize("changes", [
    {"unit": "crore"}, {"frequency": "D"}, {"horizon_hours": 71},
    {"timestamp_semantics": "interval_start"}, {"flow_scope": "includes_maturities"},
    {"confidence_level": 95}, {"as_of": "2026-10-15T00:00:00Z"},
    {"as_of": "2026-10-14T23:00:00"},
])
def test_request_semantics_rejected(request_data, changes):
    provider = FixtureProvider()
    with pytest.raises(IntegrationError):
        infer_shadow(replace(request_data, **changes), provider)
    assert provider.calls == 0


@pytest.mark.parametrize("size", [167, 168, 191, 192, 336, 5000, 5001])
def test_history_lengths(request_data, size):
    index = pd.date_range(end=request_data.as_of, periods=size, freq="h")
    records = [{"timestamp": t.isoformat(), "deposits": 1., "withdrawals": 1.} for t in index]
    candidate = replace(request_data, history=records)
    if 168 <= size <= 5000:
        assert len(candidate.validate()) == size
    else:
        with pytest.raises(IntegrationError):
            candidate.validate()


@pytest.mark.parametrize("bad", [True, "100", None, -1., np.nan, np.inf, -np.inf])
def test_bad_historical_amounts(request_data, bad):
    history = [dict(r) for r in request_data.history]
    history[0]["deposits"] = bad
    with pytest.raises(IntegrationError):
        replace(request_data, history=history).validate()


@pytest.mark.parametrize("change", ["missing", "duplicate", "reversed", "extra_field"])
def test_history_schema_and_continuity(request_data, change):
    history = [dict(r) for r in request_data.history]
    if change == "missing":
        del history[5]
    elif change == "duplicate":
        history[5] = dict(history[4])
    elif change == "reversed":
        history.reverse()
    else:
        history[0]["cash"] = 100000
    with pytest.raises(IntegrationError):
        replace(request_data, history=history).validate()


@pytest.mark.parametrize("defect", [
    "nan", "inf", "negative", "boolean", "text", "missing_target", "wrong_type",
    "short", "matrix", "naive", "misaligned", "duplicate", "reversed", "inverted", "model_id",
])
def test_invalid_outputs_are_not_clipped_or_accepted(request_data, defect):
    provider = FixtureProvider()
    predict = provider.predict

    def broken(*args, **kwargs):
        outputs = predict(*args, **kwargs)
        target = outputs["deposits"]
        if defect in ("nan", "inf", "negative"):
            target.mean.iloc[0] = {"nan": np.nan, "inf": np.inf, "negative": -1.}[defect]
        elif defect in ("boolean", "text"):
            target.mean = target.mean.astype(object)
            target.mean.iloc[0] = True if defect == "boolean" else "1000"
        elif defect == "missing_target":
            del outputs["withdrawals"]
        elif defect == "wrong_type":
            outputs["deposits"] = None
        elif defect == "short":
            target.mean = target.mean.iloc[:-1]
        elif defect == "matrix":
            target.mean = pd.DataFrame({"x": target.mean})
        elif defect == "naive":
            target.mean.index = target.mean.index.tz_localize(None)
        elif defect == "misaligned":
            target.mean.index += pd.DateOffset(hours=1)
        elif defect == "duplicate":
            target.mean.index = pd.DatetimeIndex([target.mean.index[0]] * 72)
        elif defect == "reversed":
            target.mean = target.mean.iloc[::-1]
        elif defect == "inverted":
            target.lower.iloc[0] = 999999
        else:
            target.model_name = "AnotherModel"
        return outputs

    provider.predict = broken
    with pytest.raises(IntegrationError) as error:
        infer_shadow(request_data, provider)
    assert error.value.inference_ran is True
    assert provider.calls == 1


@pytest.mark.parametrize("exception, code", [(RuntimeError, "INFERENCE_FAILED"), (TimeoutError, "TIMEOUT")])
def test_explicit_provider_failures(request_data, exception, code):
    provider = FixtureProvider()

    def fail(*args, **kwargs):
        raise exception("private-path-must-not-be-returned")

    provider.predict = fail
    with pytest.raises(IntegrationError) as error:
        infer_shadow(request_data, provider)
    assert error.value.code == code
    assert error.value.inference_ran is True
    assert "private-path" not in str(error.value)


def test_response_revalidated_before_backend_shape_conversion(request_data):
    output = infer_shadow(request_data, FixtureProvider())
    output.response.predictions[0] = replace(
        output.response.predictions[0], net=replace(output.response.predictions[0].net, mean=123.)
    )
    with pytest.raises(IntegrationError, match="Inconsistent net"):
        adapt_to_backend_state(output.response)


def test_only_explicit_synthetic_usd_fixture_can_match_usd_request(request_data):
    provider = FixtureProvider(training_currency="USD")
    output = infer_shadow(replace(request_data, currency="USD"), provider)
    assert output.response.currency == "USD"
    assert provider.calls == 1
    assert request_data.flow_scope == FLOW_SCOPE


def test_equivalent_ist_forecast_indexes_are_normalized(request_data):
    provider = FixtureProvider()
    predict = provider.predict

    def ist(*args, **kwargs):
        outputs = predict(*args, **kwargs)
        for output in outputs.values():
            for series in (output.mean, output.lower, output.upper):
                series.index = series.index.tz_convert("Asia/Kolkata")
        return outputs

    provider.predict = ist
    result = infer_shadow(request_data, provider)
    assert result.net_rows[0]["timestamp"] == "2026-10-14T18:30:00Z"


def test_elapsed_budget_reports_failure(request_data, monkeypatch):
    ticks = iter([0., 3.])
    monkeypatch.setattr(shadow.time, "perf_counter", lambda: next(ticks))
    with pytest.raises(IntegrationError) as error:
        infer_shadow(request_data, FixtureProvider())
    assert error.value.code == "TIMEOUT"
    assert error.value.inference_ran is True


def test_adapter_cannot_infer_currency_from_default(request_data):
    from reserve_juggler_ml.integration.adapter import format_forecast_response

    outputs = FixtureProvider().predict(
        request_data.validate(), periods=72, alpha=0.05, frequency="h"
    )
    dep, wdr = outputs["deposits"], outputs["withdrawals"]
    with pytest.raises(IntegrationError, match="currency"):
        format_forecast_response(
            dep.mean, dep.lower, dep.upper, wdr.mean, wdr.lower, wdr.upper,
            as_of=request_data.as_of,
        )


def test_blocked_provider_times_out_and_circuit_never_restarts_it(
    request_data, monkeypatch
):
    executor = shadow.ShadowExecutor(timeout=0.25)
    monkeypatch.setattr(shadow, "_EXECUTOR", executor)
    provider = FixtureProvider()
    release = threading.Event()
    calls = []
    original = provider.predict

    def blocked(*args, **kwargs):
        calls.append(True)
        if not release.wait(3):
            raise TimeoutError("bounded regression cleanup")
        return original(*args, **kwargs)

    provider.predict = blocked
    try:
        began = time.monotonic()
        with pytest.raises(IntegrationError) as error:
            infer_shadow(request_data, provider)
        assert error.value.code == "TIMEOUT"
        assert error.value.inference_ran is True
        assert time.monotonic() - began < 1.0
        worker = executor._worker
        assert worker.is_alive() and worker.daemon
        began = time.monotonic()
        for _ in range(20):
            with pytest.raises(IntegrationError) as error:
                infer_shadow(request_data, FixtureProvider())
            assert error.value.code == "CIRCUIT_OPEN"
            assert error.value.inference_ran is False
            assert executor._worker is worker
        assert time.monotonic() - began < 0.5
        assert len(calls) == 1
    finally:
        release.set()
        executor._worker.join(2)
    assert not executor._worker.is_alive()
    # Finishing late never silently recovers the provider or publishes results.
    with pytest.raises(IntegrationError) as error:
        infer_shadow(request_data, provider)
    assert error.value.code == "CIRCUIT_OPEN"


@pytest.mark.parametrize("finished_at, expected_code", [
    (1.999, None), (2.001, "TIMEOUT")
])
def test_completion_at_deadline_uses_real_result_or_rejects_late_result(
    request_data, monkeypatch, finished_at, expected_code
):
    # Deterministic clock: the worker's complete validated result lands just
    # before/after the 2s deadline, regardless of the scheduler's wall time.
    actual_counter = time.perf_counter
    monkeypatch.setattr(shadow, "time", SimpleNamespace(
        perf_counter=actual_counter,
        monotonic=lambda: finished_at
        if threading.current_thread().name == "rj-ml-shadow" else 0.,
    ))
    provider = FixtureProvider()
    if expected_code:
        with pytest.raises(IntegrationError) as error:
            infer_shadow(request_data, provider)
        assert error.value.code == expected_code
    else:
        result = infer_shadow(request_data, provider)
        assert result.response.predictions[0].net.mean == 9900
        assert provider.calls == 1


def test_blocked_metadata_is_also_inside_the_deadline(request_data, monkeypatch):
    executor = shadow.ShadowExecutor(timeout=0.25)
    monkeypatch.setattr(shadow, "_EXECUTOR", executor)
    release, entered = threading.Event(), threading.Event()

    class BlockedMetadata:
        @property
        def spec(self):
            entered.set()
            if not release.wait(3):
                raise TimeoutError()
            return None

    try:
        with pytest.raises(IntegrationError) as error:
            infer_shadow(request_data, BlockedMetadata())
        assert error.value.code == "TIMEOUT"
        assert error.value.inference_ran is False
        assert entered.is_set()
    finally:
        release.set()
        executor._worker.join(2)
    assert not executor._worker.is_alive()
