"""Hourly treasury planning. All account movements here are simulations."""

import copy
import hashlib
import io
import math
from functools import lru_cache

import numpy as np
import pandas as pd

from liquidity_forecasting.model import (
    forecast_currency_with_intervals,
    seasonal_naive_fallback,
)
from liquidity_forecasting.planning import (
    analyze,
    apply_planning,
    configuration,
    evaluate,
    moment,
    scheduled,
    timeline,
)

DEFAULT_POLICY = {
    "minimum_buffer": 10_000_000,
    "annual_yield": 5.0,
    "confidence": 95,
    "lock_hours": 24,
    "withdrawal_stress": 0,
    "auto_sweep": False,
}


def sample_history():
    """Fixed, reproducible demonstration; timestamps are explicitly UTC."""
    dates = pd.date_range(end="2026-10-18 08:00", periods=24 * 42, freq="h")
    rng = np.random.default_rng(42)
    phase = (dates.hour.to_numpy() - 8) * np.pi / 12
    deposits = (
        10_000_000 + 1_400_000 * np.sin(phase) + rng.normal(0, 150_000, len(dates))
    )
    withdrawals = (
        9_950_000 + 1_700_000 * np.sin(phase - 0.8) + rng.normal(0, 150_000, len(dates))
    )
    return pd.DataFrame(
        {
            "timestamp": dates.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "deposits": deposits.round(2),
            "withdrawals": withdrawals.round(2),
        }
    ).to_dict("records")


def initial_state():
    return {
        "revision": 0,
        "currency": "INR",
        "schema_version": 2,
        "cash": 100_000_000.0,
        "vault": 250_000_000.0,
        "earned": 0.0,
        "policy": dict(DEFAULT_POLICY),
        "history": sample_history(),
        "source": "Indian banking demo · INR",
        "ledger": [],
        "tranches": [],
    }


def validate_history(records):
    if not isinstance(records, list) or not 168 <= len(records) <= 5000:
        raise ValueError("Provide between 168 and 5,000 consecutive hourly records.")
    frame = pd.DataFrame(records)
    if list(frame.columns) != ["timestamp", "deposits", "withdrawals"]:
        raise ValueError(
            "CSV columns must be timestamp,deposits,withdrawals in that order."
        )
    if (
        not frame["timestamp"]
        .astype(str)
        .str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", regex=True)
        .all()
    ):
        raise ValueError(
            "Include an explicit timezone offset: +05:30 for IST or Z for UTC."
        )
    times = pd.to_datetime(frame["timestamp"], utc=True, errors="raise", format="mixed")
    if (
        times.isna().any()
        or times.duplicated().any()
        or not times.is_monotonic_increasing
    ):
        raise ValueError("Timestamps must be valid, unique, and sorted ascending.")
    if not (times.diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("Records must be exactly one hour apart, without gaps.")
    if not ((times.dt.second == 0) & (times.dt.microsecond == 0)).all():
        raise ValueError(
            "Hourly timestamps must not contain seconds or fractional seconds."
        )
    for column in ["deposits", "withdrawals"]:
        if frame[column].map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise ValueError("Cashflows must be numeric amounts, not booleans.")
        values = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(values).all() or (values < 0).any() or (values > 1e12).any():
            raise ValueError(
                "Cashflows must be finite amounts between 0 and 1 trillion."
            )
        frame[column] = values.astype(float)
    frame["timestamp"] = times.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.to_dict("records")


def parse_csv(text):
    if not isinstance(text, str) or len(text) > 1_000_000:
        raise ValueError("CSV must be text and smaller than 1 MB.")
    try:
        frame = pd.read_csv(io.StringIO(text), keep_default_na=True)
        return validate_history(frame.to_dict("records"))
    except (TypeError, OverflowError) as error:
        raise ValueError("Unable to parse CSV dates or numeric values.") from error


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_POLICY):
        raise ValueError("Supply all policy fields, without additional fields.")
    limits = {
        "minimum_buffer": (0, 1e10),
        "annual_yield": (0, 20),
        "confidence": (90, 99),
        "lock_hours": (1, 72),
        "withdrawal_stress": (0, 100),
    }
    result = dict(policy)
    for field, (minimum, maximum) in limits.items():
        value = policy[field]
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"{field} must be a number.")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"{field} must be between {minimum:g} and {maximum:g}.")
    if policy["confidence"] not in (90, 95, 99):
        raise ValueError("Confidence must be 90, 95, or 99.")
    if int(policy["lock_hours"]) != policy["lock_hours"]:
        raise ValueError("Lock hours must be a whole number.")
    if not isinstance(policy["auto_sweep"], bool):
        raise ValueError("auto_sweep must be true or false.")
    result["lock_hours"] = int(policy["lock_hours"])
    return result


@lru_cache(maxsize=12)
def fit_hourly(history_csv, confidence):
    frame = pd.read_csv(io.StringIO(history_csv), parse_dates=[0], index_col=0)
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None)
    frame = frame.asfreq("h")
    net = pd.DataFrame({"INR": frame.deposits - frame.withdrawals}, index=frame.index)
    result = forecast_currency_with_intervals(
        net.tail(24 * 28),
        "INR",
        periods=72,
        order=(1, 0, 0),
        seasonal=(1, 0, 0, 24),
        alpha=1 - confidence / 100,
        frequency="h",
    )
    # Gross withdrawal profile provides an observable basis for stress overlays.
    profile = (
        frame.tail(24 * 14).groupby(frame.tail(24 * 14).index.hour).withdrawals.mean()
    )
    rows = []
    for date, mean, lower, upper in zip(
        result.mean.index, result.mean, result.lower, result.upper
    ):
        if not all(math.isfinite(float(v)) for v in (mean, lower, upper)):
            raise ValueError("The model returned non-finite predictions.")
        rows.append(
            {
                "timestamp": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "mean": float(mean),
                "lower": float(lower),
                "upper": float(upper),
                "withdrawals": float(profile[date.hour]),
            }
        )
    # Honest holdout baseline, not a claimed SARIMAX accuracy score.
    values = net.INR.to_numpy()
    mae = float(np.mean(np.abs(values[-168:] - values[-192:-24])))
    return rows, result.model_name, result.converged, mae


def forecast(state):
    csv = pd.DataFrame(state["history"]).to_csv(index=False)
    return fit_hourly(csv, state["policy"]["confidence"])


def gross_forecast(state):
    """Independent deposit/withdrawal seasonal forecasts; not SARIMAX scores."""
    frame = pd.DataFrame(state["history"])
    index = pd.to_datetime(frame.timestamp, utc=True)
    results = {}
    for column in ("deposits", "withdrawals"):
        series = pd.Series(frame[column].to_numpy(), index=index)
        results[column] = seasonal_naive_fallback(
            series, 72, 1 - state["policy"]["confidence"] / 100, 24, "h"
        )
    rows = []
    for i, timestamp in enumerate(results["deposits"].mean.index):
        row = {"timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")}
        for column, result in results.items():
            row[column] = max(0, float(result.mean.iloc[i]))
            row[column + "_lower"] = max(0, float(result.lower.iloc[i]))
            row[column + "_upper"] = max(0, float(result.upper.iloc[i]))
        rows.append(row)
    return {
        "model": "Independent seasonal-naive gross forecasts",
        "rows": rows,
        "note": "Gross forecasts are separate estimates. The net SARIMAX forecast "
        "is authoritative for the reconciled planning path.",
    }


def reserve_plan(cash, rows, policy):
    """Reserve the worst lower-envelope drawdown until a new sweep matures.

    Sum of pointwise lower bounds is a conservative planning envelope, NOT
    a calibrated confidence interval for an entire path or payout guarantee.
    Existing locked vault funds are deliberately excluded from available cash.
    """
    cumulative = 0.0
    lowest = 0.0
    stress_total = 0.0
    for row in rows[: policy["lock_hours"]]:
        stress = row["withdrawals"] * policy["withdrawal_stress"] / 100
        stress_total += stress
        cumulative += row["lower"] - stress
        lowest = min(lowest, cumulative)
    drawdown = -lowest
    required = math.ceil((policy["minimum_buffer"] + drawdown) * 100) / 100
    sweep = math.floor(max(0, cash - required) * 100) / 100
    return {
        "required": required,
        "drawdown": drawdown,
        "sweep": sweep,
        "shortfall": max(0, required - cash),
        "stress_outflow": stress_total,
        "daily_yield": sweep * policy["annual_yield"] / 100 / 365,
        "retained": cash - sweep,
    }


def snapshot(state):
    rows, model, converged, mae = forecast(state)
    policy = state["policy"]
    plan = reserve_plan(state["cash"], rows, policy)
    timed = evaluate(
        state["cash"],
        timeline(state, {"withdrawals": policy["withdrawal_stress"]}, rows),
        policy["minimum_buffer"] + configuration(state)["risk_buffer"],
        policy["lock_hours"],
        now=moment(state["history"][-1]["timestamp"]),
    )
    plan["sweep"] = min(plan["sweep"], timed["eligible"])
    plan["required"] = max(plan["required"], timed["required"])
    plan["retained"] = state["cash"] - plan["sweep"]
    plan["shortfall"] = max(plan["shortfall"], timed["shortfall"])
    plan["daily_yield"] = plan["sweep"] * policy["annual_yield"] / 100 / 365
    cumulative = lower_sum = upper_sum = 0.0
    chart = []
    for row in rows:
        stress = row["withdrawals"] * policy["withdrawal_stress"] / 100
        cumulative += row["mean"] - stress
        lower_sum += row["lower"] - stress
        upper_sum += row["upper"] - stress
        chart.append(
            {
                **row,
                "balance": state["cash"] + cumulative,
                "lower_balance": state["cash"] + lower_sum,
                "upper_balance": state["cash"] + upper_sum,
            }
        )
    return {
        **{k: v for k, v in state.items() if k != "history"},
        "as_of": state["history"][-1]["timestamp"],
        "history_count": len(state["history"]),
        "history": state["history"][-168:],
        "forecast": chart,
        "gross_forecast": gross_forecast(state),
        "plan": plan,
        "model": model,
        "converged": converged,
        "baseline_mae": mae,
        "gross_hourly": float(
            np.mean([r["deposits"] + r["withdrawals"] for r in state["history"][-24:]])
        ),
        "daily_vault_yield": (
            (state["vault"] - sum(t["amount"] for t in state["tranches"]))
            * policy["annual_yield"]
            / 100
            / 365
            + sum(
                t["amount"] * t["annual_yield"] / 100 / 365 for t in state["tranches"]
            )
        ),
        "mode": "simulation",
        "intelligence": analyze(state),
    }


def event(state, kind, amount, description, timestamp=None):
    state["ledger"].insert(
        0,
        {
            "id": f"RJ-{state['revision'] + 1:04d}-{len(state['ledger']) + 1:04d}",
            "timestamp": timestamp or state["history"][-1]["timestamp"],
            "type": kind,
            "amount": round(amount, 2),
            "description": description,
            "status": "Simulated",
        },
    )
    state["ledger"] = state["ledger"][:1000]


def sweep(state):
    rows, *_ = forecast(state)
    plan = reserve_plan(state["cash"], rows, state["policy"])
    timed = evaluate(
        state["cash"],
        timeline(state, {"withdrawals": state["policy"]["withdrawal_stress"]}, rows),
        state["policy"]["minimum_buffer"] + configuration(state)["risk_buffer"],
        state["policy"]["lock_hours"],
        now=moment(state["history"][-1]["timestamp"]),
    )
    amount = min(plan["sweep"], timed["eligible"])
    if amount < 0.01:
        raise ValueError("No eligible surplus. Keep cash available for the reserve.")
    maturity = pd.Timestamp(state["history"][-1]["timestamp"]) + pd.Timedelta(
        hours=state["policy"]["lock_hours"]
    )
    state["cash"] = round(state["cash"] - amount, 2)
    state["vault"] = round(state["vault"] + amount, 2)
    state["tranches"].append(
        {
            "amount": amount,
            "matures": maturity.isoformat(),
            "annual_yield": state["policy"]["annual_yield"],
            "hours": state["policy"]["lock_hours"],
        }
    )
    event(
        state,
        "Sweep",
        amount,
        "Buffer → vault · matures "
        + maturity.tz_convert("Asia/Kolkata").strftime("%d %b %H:%M IST"),
    )


def advance(state):
    """One explicit sandbox hour; observations are simulated, never called live."""
    rows, *_ = forecast(state)
    first = rows[0]
    timestamp = first["timestamp"]
    pending = scheduled(state)
    seed = int(hashlib.sha256(timestamp.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    withdrawals = first["withdrawals"] * (
        1 + state["policy"]["withdrawal_stress"] / 100
    )
    deposits = max(0, first["withdrawals"] + first["mean"] + rng.normal(0, 300_000))
    net = round(deposits - withdrawals, 2)
    # Merge real simulated obligations, gross hourly flows and contractual
    # maturities onto one clock. Outflows win ties; no end-hour netting.
    movements = [
        {
            "timestamp": timestamp,
            "flow": -round(withdrawals, 2),
            "kind": "withdrawal",
            "label": "Simulated hourly withdrawals",
        },
        {
            "timestamp": timestamp,
            "flow": round(deposits, 2),
            "kind": "deposit",
            "label": "Simulated hourly deposits",
        },
    ]
    due = [e for e in pending if moment(e["timestamp"]) <= moment(timestamp)]
    state["scheduled"] = [e for e in pending if e not in due]
    for obligation in due:
        sign = 1 if obligation["kind"] in ("deposit", "settlement") else -1
        movements.append(
            {
                "timestamp": obligation["timestamp"],
                "flow": sign * obligation["amount"],
                "kind": "scheduled",
                "label": obligation["label"],
            }
        )
    remaining = []
    for tranche in state["tranches"]:
        if moment(tranche["matures"]) <= moment(timestamp):
            interest = round(
                tranche["amount"]
                * tranche["annual_yield"]
                / 100
                * tranche["hours"]
                / (365 * 24),
                2,
            )
            movements.append(
                {
                    "timestamp": tranche["matures"],
                    "flow": tranche["amount"] + interest,
                    "kind": "maturity",
                    "label": "Contractual maturity",
                    "principal": tranche["amount"],
                    "interest": interest,
                }
            )
        else:
            remaining.append(tranche)
    for movement in sorted(
        movements, key=lambda m: (moment(m["timestamp"]), m["flow"] >= 0)
    ):
        state["cash"] = round(state["cash"] + movement["flow"], 2)
        if movement["kind"] == "maturity":
            state["vault"] = round(state["vault"] - movement["principal"], 2)
            state["earned"] = round(state["earned"] + movement["interest"], 2)
            event(
                state,
                "Maturity",
                movement["principal"],
                movement["label"],
                movement["timestamp"],
            )
            event(
                state,
                "Interest",
                movement["interest"],
                "Contracted interest",
                movement["timestamp"],
            )
        elif movement["kind"] == "scheduled":
            event(
                state,
                "Scheduled event",
                movement["flow"],
                movement["label"],
                movement["timestamp"],
            )
        gap = max(0, state["policy"]["minimum_buffer"] - state["cash"])
        if gap:
            state["policy"]["auto_sweep"] = False
            event(
                state,
                "Shortfall",
                gap,
                "Funding needed at payment time; automation halted",
                movement["timestamp"],
            )
    state["tranches"] = remaining
    state["history"].append(
        {
            "timestamp": timestamp,
            "deposits": round(deposits, 2),
            "withdrawals": round(withdrawals, 2),
        }
    )
    state["history"] = state["history"][-5000:]
    if not state["source"].endswith(" + simulated hours"):
        state["source"] += " + simulated hours"
    event(state, "Cashflow", net, "Simulated hour · deposits less withdrawals")
    if state["cash"] < 0:
        deficit = -state["cash"]
        event(
            state,
            "Shortfall",
            deficit,
            "Unfunded payout requirement; automation halted",
        )
        state["policy"]["auto_sweep"] = False
    if state["policy"]["auto_sweep"]:
        if analyze(state)["optimized"]["suggested"] > 0:
            apply_planning(state, "planning_optimize", {})
            event(
                state,
                "Sweep",
                state["tranches"][-1]["amount"],
                "Optimized automatic simulated sweep",
            )


def apply_action(original, action, payload):
    request_id = payload.get("request_id")
    fingerprint = hashlib.sha256(json_payload(action, payload).encode()).hexdigest()
    if request_id is not None:
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise ValueError("request_id must contain 1–128 characters.")
        previous = original.get("operations", {}).get(request_id)
        if previous:
            if previous != fingerprint:
                raise ValueError(
                    "request_id was already used with a different payload."
                )
            return copy.deepcopy(original)
    if payload.get("revision") != original["revision"]:
        raise ValueError(
            "The workspace changed. Refresh and review the latest amounts."
        )
    state = copy.deepcopy(original)
    before = analyze(original)
    if action.startswith("planning_"):
        apply_planning(state, action, payload)
    elif action == "sweep":
        sweep(state)
    elif action == "advance":
        advance(state)
    elif action == "policy":
        state["policy"] = validate_policy(payload.get("policy"))
        event(
            state, "Policy", 0, "Reserve policy updated; recommendations recalculated"
        )
    elif action == "import":
        if state["tranches"]:
            raise ValueError(
                "Reset the sandbox before importing while sweeps are locked."
            )
        records = parse_csv(payload.get("csv"))
        state["history"] = records
        state.pop("scheduled", None)
        state["scheduled"] = scheduled(state)
        state["source"] = "Imported cashflows · simulated balances"
        state["policy"]["auto_sweep"] = False
        event(state, "Import", 0, f"Validated {len(records):,} hourly observations")
    elif action == "reset":
        state = initial_state()
    else:
        raise ValueError("Unknown action.")
    if not action.startswith("planning_") and action != "reset":
        after = analyze(state)
        state.setdefault("decisions", []).insert(
            0,
            {
                "timestamp": state["history"][-1]["timestamp"],
                "action": action,
                "cash": state["cash"],
                "reserve": after["selected"]["required"],
                "investment": after["selected"]["suggested"],
                "reason": f"{action}: " + after["selected"]["reason"],
                "before": before["selected"],
                "after": after["selected"],
            },
        )
        state["decisions"] = state["decisions"][:200]
    state["revision"] = original["revision"] + 1
    if request_id is not None:
        state.setdefault("operations", {})[request_id] = fingerprint
    locked = sum(t["amount"] for t in state["tranches"])
    if locked > state["vault"] + 0.01:
        raise ValueError(
            "Reconciliation failed: locked principal exceeds vault balance."
        )
    return state


def json_payload(action, payload):
    import json

    return json.dumps([action, payload], sort_keys=True, allow_nan=False)
