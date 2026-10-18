"""Paired gross inference with explicit provenance and no treasury dependency."""

import threading
import time
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from reserve_juggler_ml.data.schemas import ForecastResponse
from reserve_juggler_ml.forecasting.base import ForecastOutput
from reserve_juggler_ml.integration.adapter import (
    adapt_to_backend_state,
    format_forecast_response,
)
from reserve_juggler_ml.integration.contract import (
    HORIZON,
    IntegrationError,
    ModelSpec,
    ShadowRequest,
)


class ShadowProvider(Protocol):
    """Backend-injected, already-loaded provider; predict must not train.

    A provider receives only UTC completed gross history, never financial state.
    It returns separate ForecastOutputs for deposits and withdrawals. Its own
    code is trusted and must not access treasury globals or locks. The boundary
    bounds the caller's wait; a timed-out daemon call is not forcibly cancelled.
    """

    spec: ModelSpec

    def predict(
        self, history: pd.DataFrame, *, periods: int, alpha: float, frequency: str
    ) -> dict[str, ForecastOutput]: ...


@dataclass
class ShadowPrediction:
    response: ForecastResponse
    net_rows: list
    gross_forecast: dict
    model_spec: ModelSpec


TIMEOUT_SECONDS = 2.0


class ShadowExecutor:
    """One daemon worker, no queue, latched circuit after timeout.

    This lock protects worker bookkeeping/startup only. The caller releases it
    before waiting; it is unrelated to treasury transaction locks.
    Recovery requires restarting the process, even if the late worker exits.
    """

    def __init__(self, timeout=TIMEOUT_SECONDS):
        if not 0 < timeout <= TIMEOUT_SECONDS:
            raise ValueError("Shadow wait must be greater than zero and at most 2s.")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._worker = None
        self._open = False

    def run(self, operation):
        done = threading.Event()
        inference_started = threading.Event()
        outcome = {}
        with self._lock:
            if self._open:
                raise IntegrationError(
                    "CIRCUIT_OPEN", "Shadow provider unavailable until process restart."
                )
            if self._worker is not None and self._worker.is_alive():
                raise IntegrationError(
                    "SHADOW_BUSY", "One shadow worker is already active; no work queued."
                )
            deadline = time.monotonic() + self.timeout

            def execute():
                try:
                    outcome["result"] = operation(inference_started)
                except BaseException as exc:
                    # Never propagate raw plugin exception text/tracebacks to
                    # request logging: metadata errors can contain private data.
                    # SystemExit/KeyboardInterrupt must not escape the daemon.
                    if isinstance(exc, IntegrationError):
                        outcome["error"] = exc
                    else:
                        outcome["error"] = IntegrationError(
                            "INTEGRATION_FAILED", "Shadow worker stopped unexpectedly.",
                            inference_ran=inference_started.is_set(),
                        )
                finally:
                    outcome["finished_at"] = time.monotonic()
                    error = outcome.get("error")
                    with self._lock:
                        if outcome["finished_at"] > deadline or (
                            isinstance(error, IntegrationError)
                            and error.code == "TIMEOUT"
                        ):
                            self._open = True
                        done.set()

            worker = threading.Thread(
                target=execute, name="rj-ml-shadow", daemon=True
            )
            self._worker = worker
            worker.start()
        # Event.wait releases its own condition lock. No treasury or executor
        # bookkeeping lock is held while the provider runs or this caller waits.
        done.wait(max(0, deadline - time.monotonic()))
        with self._lock:
            if not done.is_set() or outcome["finished_at"] > deadline:
                self._open = True
                raise IntegrationError(
                    "TIMEOUT", "Shadow deadline exceeded; circuit open until restart.",
                    inference_ran=inference_started.is_set(),
                )
        if "error" in outcome:
            raise outcome["error"]
        return outcome["result"]


_EXECUTOR = ShadowExecutor()


def infer_shadow(request: ShadowRequest, provider: ShadowProvider):
    """Bound the entire optional operation, including provider metadata access."""
    return _EXECUTOR.run(lambda started: _infer_shadow(request, provider, started))


def _infer_shadow(request, provider, inference_started):
    history = request.validate()
    if provider is None:
        raise IntegrationError(
            "MODEL_UNAVAILABLE", "No reviewed runtime provider configured."
        )
    if not isinstance(getattr(provider, "spec", None), ModelSpec):
        raise IntegrationError(
            "INVALID_MODEL_METADATA", "Explicit model provenance required."
        )
    spec = provider.spec
    spec.validate_for(request)
    start = time.perf_counter()
    # Never call fit(), deserialize research pickles or select/train a model here.
    try:
        inference_started.set()
        outputs = provider.predict(
            history.copy(deep=True), periods=HORIZON,
            alpha=round(1 - request.confidence_level, 2), frequency="h",
        )
    except TimeoutError as exc:
        raise IntegrationError(
            "TIMEOUT", "Shadow inference timed out.", inference_ran=True
        ) from exc
    except Exception as exc:
        # The optional plugin boundary quarantines provider errors. Never report
        # success or expose raw exception text (which may contain private paths).
        raise IntegrationError(
            "INFERENCE_FAILED", "Shadow provider failed; legacy retained.",
            inference_ran=True,
        ) from exc
    elapsed = (time.perf_counter() - start) * 1000
    if elapsed > 2000:
        raise IntegrationError(
            "TIMEOUT", "Shadow inference exceeded the 2,000ms budget.",
            inference_ran=True,
        )
    try:
        return _validated_prediction(request, spec, outputs, elapsed)
    except IntegrationError as exc:
        exc.inference_ran = True
        raise


def _validated_prediction(request, spec, outputs, elapsed):
    if not isinstance(outputs, dict) or set(outputs) != {"deposits", "withdrawals"}:
        raise IntegrationError(
            "INVALID_PREDICTION", "Separate gross target outputs required."
        )
    for output in outputs.values():
        if not isinstance(output, ForecastOutput) or output.model_name != spec.model_id:
            raise IntegrationError(
                "INVALID_PREDICTION", "Unexpected forecast output/model identity."
            )
    deposits, withdrawals = outputs["deposits"], outputs["withdrawals"]
    response = format_forecast_response(
        deposits.mean, deposits.lower, deposits.upper,
        withdrawals.mean, withdrawals.lower, withdrawals.upper,
        as_of=request.as_of, confidence_level=request.confidence_level,
        model_name=spec.model_id, model_version=spec.version,
        currency=request.currency, training_cutoff=spec.trained_through,
        latency_ms=elapsed,
    )
    net_rows, gross = adapt_to_backend_state(response)
    return ShadowPrediction(response, net_rows, gross, spec)
