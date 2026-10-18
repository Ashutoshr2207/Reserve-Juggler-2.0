# Reserve Juggler AI/ML Integration Contract

**Version:** 1.0.0-draft  
**Audit Date:** 18 October 2026  
**Status:** Canonical AI/ML Integration Specification  
**Scope:** Interface contract between `reserve_juggler_ml` and the backend treasury engine (`server.py`, `treasury.py`, `planning.py`).

---

## 1. Principles of Interface Separation

1. **AI/ML Scope (Advisory Only):** The AI/ML module produces statistical estimates, point forecasts, calibrated prediction intervals, and liquidity-risk quantiles. It has zero authority over accounting balances, bank transfers, or investment allocations.
2. **Treasury Engine Scope (Execution Authority):** The backend owns liquid cash balances, vault holdings, statutory reserve calculations, payment ordering, term investment eligibility, fee deductions, and audit ledger persistence.
3. **No Implicit Assumptions:** Currencies, units, timezones, and prediction origins must be explicitly stated in data transfers.

---

## 2. Temporal & Monetary Conventions

| Attribute | Specification | Violation Action |
|---|---|---|
| **Currency** | Strictly `INR` (Indian Rupee) for primary application. | Reject with HTTP 400 / ValueError if currency != "INR". No implicit FX conversion. |
| **Monetary Units** | Base units (Rupees), positive floats rounded to 2 decimal places. | Reject negative deposits or withdrawals. |
| **Timestamp Format** | ISO 8601 string: `YYYY-MM-DDTHH:MM:SSZ` (UTC normalized). | Require explicit offset (`Z` or `+05:30`); normalize to UTC instant. |
| **Sampling Frequency** | Strictly hourly (`freq="h"`), exactly 3,600 seconds between points. | Reject non-consecutive or missing hourly records. |
| **Forecast Horizon** | Exactly 72 consecutive hours ($t+1$ through $t+72$). | Output must contain exactly 72 records matching horizon grid. |

---

## 3. Data Ingestion Contract (`ForecastRequest`)

The backend sends observation history and policy configuration to the forecasting adapter:

```json
{
  "currency": "INR",
  "as_of": "2026-10-18T08:00:00Z",
  "history": [
    {
      "timestamp": "2026-10-01T00:00:00Z",
      "deposits": 10500000.00,
      "withdrawals": 9800000.00
    }
  ],
  "policy": {
    "confidence_level": 0.95,
    "horizons": [6, 24, 48, 72]
  }
}
```

### Constraints on Input:
- `history`: Array of minimum 168 and maximum 5,000 consecutive hourly records.
- `as_of`: Matches the timestamp of the last element in `history`.
- `confidence_level`: One of `0.90`, `0.95`, or `0.99`.

---

## 4. Forecast Output Contract (`ForecastResponse`)

The forecasting adapter returns validated point forecasts, uncertainty bounds, model metadata, and liquidity-risk quantiles:

```json
{
  "contract_version": "1.0.0",
  "currency": "INR",
  "as_of": "2026-10-18T08:00:00Z",
  "forecast_origin": "2026-10-18T08:00:00Z",
  "horizon_hours": 72,
  "confidence_level": 0.95,
  "model_metadata": {
    "model_name": "XGBoostDirect72",
    "model_version": "1.0.0",
    "fallback_used": false,
    "fallback_reason": null,
    "training_cutoff": "2026-10-18T08:00:00Z",
    "latency_ms": 14.2
  },
  "predictions": [
    {
      "step": 1,
      "timestamp": "2026-10-18T09:00:00Z",
      "deposits": {
        "mean": 11200000.00,
        "lower": 10100000.00,
        "upper": 12300000.00
      },
      "withdrawals": {
        "mean": 10400000.00,
        "lower": 9500000.00,
        "upper": 11300000.00
      },
      "net": {
        "mean": 800000.00,
        "lower": -1200000.00,
        "upper": 2800000.00
      }
    }
  ],
  "liquidity_risk": [
    {
      "horizon_hours": 6,
      "max_cumulative_deficit_q95": 2450000.00,
      "max_cumulative_deficit_q99": 4120000.00
    },
    {
      "horizon_hours": 24,
      "max_cumulative_deficit_q95": 8500000.00,
      "max_cumulative_deficit_q99": 14200000.00
    },
    {
      "horizon_hours": 48,
      "max_cumulative_deficit_q95": 12100000.00,
      "max_cumulative_deficit_q99": 19800000.00
    },
    {
      "horizon_hours": 72,
      "max_cumulative_deficit_q95": 15400000.00,
      "max_cumulative_deficit_q99": 24100000.00
    }
  ],
  "warnings": []
}
```

---

## 5. Backward Compatibility Adapter for Existing Backend

The existing `server.py` expects:
- `snapshot["forecast"]`: Array of 72 `NetRow` dictionaries (`mean`, `lower`, `upper`, `withdrawals`, etc.).
- `snapshot["gross_forecast"]`: Object containing `model`, `note`, and `rows` of 72 `GrossRow` dictionaries.

The `reserve_juggler_ml.integration.adapter` module provides a drop-in converter that translates `ForecastResponse` directly into the existing `State` fields without requiring immediate modifications to `server.py` or `web/app.js`.

---

## 6. Failure & Fallback Handling

1. **Graceful Fallback:** If the primary ML candidate (e.g., XGBoost) encounters missing lag values, inference timeouts (> 2,000 ms), or numerical anomalies, it must automatically execute the `SeasonalNaiveFallback`.
2. **Metadata Transparency:** When fallback occurs, `fallback_used` must be set to `true`, and `fallback_reason` must record the exact exception string (e.g., `"Inference timeout exceeded; seasonal-naïve fallback deployed"`).
3. **Fail-Closed Safety:** Under no circumstances shall an empty or corrupted forecast be returned. If both ML and fallback fail, an explicit `ForecastingException` is raised, triggering HTTP 500 without mutating financial state.
