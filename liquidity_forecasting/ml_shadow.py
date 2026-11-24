"""Optional ML diagnostics. No prediction from here enters treasury planning."""

import copy
import logging
import os

logger = logging.getLogger(__name__)


def capture_inputs(state):
    """Call under the treasury lock; retain only independently owned ML inputs."""
    return {
        "currency": state.get("currency"),
        "history": copy.deepcopy(state["history"]),
        "policy": {"confidence": state["policy"]["confidence"]},
    }


def diagnostics(state, provider=None):
    """Evaluate a backend-injected provider only after compatibility gates.

    No automatic research artifact loader: existing local USD files have no
    reviewed serving manifest for the INR bucket-end application. No source
    path hacks or optional ML imports are needed for the default application.
    """
    setting = os.environ.get("RJ_ML_SHADOW_ENABLED", "false").strip().lower()
    result = {
        "contract_version": "shadow-1.0",
        "enabled": setting == "true",
        "status": "disabled",
        "code": "SHADOW_DISABLED",
        "message": "Shadow mode is disabled; existing treasury forecast retained.",
        "authoritative_forecast": "existing_treasury",
        "controls_treasury": False,
        "inference_ran": False,
        "input_currency": state.get("currency"),
        "model_currency": None,
        "model": None,
        "warnings": [],
    }
    if setting not in {"true", "false"}:
        return dict(
            result, status="failed", code="INVALID_CONFIGURATION",
            message="RJ_ML_SHADOW_ENABLED must be true or false.",
        )
    if not result["enabled"]:
        return result
    if state.get("currency") not in ("INR", "USD"):
        return dict(
            result, status="skipped", code="UNSUPPORTED_CURRENCY",
            message="Explicit supported input currency required.",
        )
    if provider is None:
        # Repository research artifacts are USD-denominated. Their filenames
        # and reports do not authorize loading, relabeling or deploying them.
        return dict(
            result, status="skipped", model_currency="USD",
            code=(
                "CURRENCY_MISMATCH"
                if state["currency"] != "USD" else "MODEL_UNAVAILABLE"
            ),
            message=(
                "Existing research artifacts are USD-trained; "
                "no reviewed runtime provider is configured."
            ),
        )
    try:
        from reserve_juggler_ml.integration.contract import (
            IntegrationError,
            ShadowRequest,
        )
        from reserve_juggler_ml.integration.shadow import infer_shadow
    except ImportError:
        return dict(
            result, status="skipped", code="ML_PACKAGE_UNAVAILABLE",
            message=(
                "Optional ML package/dependencies unavailable; "
                "existing forecast retained."
            ),
        )
    except Exception:
        logger.exception("Optional ML package initialization failed")
        return dict(
            result, status="failed", code="INTEGRATION_FAILED",
            message="Shadow package initialization failed; existing forecast retained.",
        )
    try:
        request = ShadowRequest(
            currency=state["currency"],
            as_of=state["history"][-1]["timestamp"],
            history=copy.deepcopy(state["history"]),
            confidence_level=state["policy"]["confidence"] / 100,
        )
        prediction = infer_shadow(request, provider)
    except IntegrationError as exc:
        status = "skipped" if exc.code in {
            "CURRENCY_MISMATCH", "CIRCUIT_OPEN", "SHADOW_BUSY"
        } else "failed"
        return dict(
            result, status=status, code=exc.code, message=str(exc),
            inference_ran=exc.inference_ran,
        )
    except Exception:
        # An optional integration defect must remain visible but must not turn
        # a valid legacy response into an outage or expose raw data/paths.
        logger.exception("Optional shadow integration failed; legacy retained")
        return dict(
            result, status="failed", code="INTEGRATION_FAILED",
            message="Shadow integration failed; existing forecast retained.",
        )
    spec = prediction.model_spec
    return dict(
        result, status="completed", code="SHADOW_VALIDATED", inference_ran=True,
        model_currency=spec.training_currency,
        model={
            "id": spec.model_id, "version": spec.version,
            "interval_method": spec.interval_method,
        },
        message="Validated shadow output discarded; existing forecast retained.",
        warnings=prediction.response.warnings,
    )
