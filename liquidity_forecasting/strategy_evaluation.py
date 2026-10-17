"""Chronological, reproducible treasury strategy evaluation; no saved balances."""

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from liquidity_forecasting.model import seasonal_naive_fallback
from liquidity_forecasting.planning import analyze, iso, moment
from liquidity_forecasting.treasury import (
    DEFAULT_POLICY,
    fit_hourly,
    initial_state,
    reserve_plan,
    validate_history,
)


def evaluation_forecast(history, confidence=95, model="fallback"):
    """Only the supplied training prefix is visible to the predictor."""
    frame = pd.DataFrame(history)
    if model == "sarimax":
        return fit_hourly(frame.to_csv(index=False), confidence)[0]
    series = pd.Series(
        (frame.deposits - frame.withdrawals).to_numpy(),
        index=pd.to_datetime(frame.timestamp, utc=True),
    )
    result = seasonal_naive_fallback(series, 72, 1 - confidence / 100, 24, "h")
    profile = (
        frame.tail(336)
        .groupby(pd.to_datetime(frame.tail(336).timestamp).dt.hour)
        .withdrawals.mean()
    )
    return [
        {
            "timestamp": iso(date.to_pydatetime()),
            "mean": float(mean),
            "lower": float(lower),
            "upper": float(upper),
            "withdrawals": float(profile[date.hour]),
        }
        for date, mean, lower, upper in zip(
            result.mean.index, result.mean, result.lower, result.upper
        )
    ]


def compare_strategies(
    history=None,
    hours=72,
    fixed_buffer=85_000_000,
    borrowing_rate=12.0,
    failure_every=0,
    model="fallback",
    predictor=None,
):
    source = (
        "seed-42 synthetic INR hourly cashflows"
        if history is None
        else "supplied hourly observations"
    )
    history = validate_history(
        history if history is not None else initial_state()["history"]
    )
    if not isinstance(hours, int) or not 1 <= hours <= len(history) - 168:
        raise ValueError(
            "Evaluation needs at least 168 training hours and a positive holdout."
        )
    if model not in ("fallback", "sarimax"):
        raise ValueError("Choose fallback or sarimax.")
    if fixed_buffer < 0 or borrowing_rate < 0 or failure_every < 0:
        raise ValueError("Evaluation assumptions must be nonnegative.")
    predictor = predictor or (lambda h: evaluation_forecast(h, model=model))
    start = len(history) - hours
    # Compute once per origin, shared by all strategies. No holdout access.
    predictions = [
        predictor(copy.deepcopy(history[:origin]))
        for origin in range(start, len(history))
    ]
    errors = [
        history[start + i]["deposits"]
        - history[start + i]["withdrawals"]
        - rows[0]["mean"]
        for i, rows in enumerate(predictions)
    ]
    results = []
    for strategy in (
        "A — Fixed cash buffer",
        "B — Existing forecast reserve",
        "C — Improved Reserve Juggler",
    ):
        state = initial_state()
        state.update(history=copy.deepcopy(history[:start]), vault=0, scheduled=[])
        fees = interest = accrued = idle = total_gap = max_gap = borrowing = (
            invested
        ) = eligible_total = 0.0
        breaches = attempts = failed = recovered = successes = 0
        recovery_pending = False
        for step, actual in enumerate(history[start:]):
            rows = predictions[step]
            if strategy.startswith("A"):
                principal = max(0, state["cash"] - fixed_buffer)
                duration, rate, fee = 24, 5.0, 0
            elif strategy.startswith("B"):
                principal = reserve_plan(state["cash"], rows, DEFAULT_POLICY)["sweep"]
                duration, rate, fee = 24, 5.0, 0
            else:
                option = analyze(state, forecast_rows=rows)["optimized"]
                principal = option["suggested"]
                duration, rate, fee = option["hours"], option["rate"], option["fee"]
            principal = np.floor(principal * 100) / 100
            eligible_total += principal
            if principal >= 0.01:
                attempts += 1
                if failure_every and attempts % failure_every == 0:
                    failed += 1
                    recovery_pending = True
                else:
                    if recovery_pending:
                        recovered += 1
                        recovery_pending = False
                    successes += 1
                    invested += principal
                    fees += fee
                    state["cash"] = round(state["cash"] - principal - fee, 2)
                    state["vault"] += principal
                    now = pd.Timestamp(state["history"][-1]["timestamp"])
                    state["tranches"].append(
                        {
                            "amount": principal,
                            "hours": duration,
                            "annual_yield": rate,
                            "started": iso(now.to_pydatetime()),
                            "matures": iso(
                                (now + pd.Timedelta(hours=duration)).to_pydatetime()
                            ),
                        }
                    )
            idle += max(0, state["cash"])
            # Same conservative convention as production: gross withdrawals
            # precede receipts and maturity redemption at an identical timestamp.
            movements = [
                (moment(actual["timestamp"]), -actual["withdrawals"]),
                (moment(actual["timestamp"]), actual["deposits"]),
            ]
            remaining = []
            for t in state["tranches"]:
                accrued += t["amount"] * t["annual_yield"] / 100 / 8760
                if moment(t["matures"]) <= moment(actual["timestamp"]):
                    earned = round(
                        t["amount"] * t["annual_yield"] / 100 * t["hours"] / 8760, 2
                    )
                    movements.append((moment(t["matures"]), t["amount"] + earned))
                    interest += earned
                    state["vault"] -= t["amount"]
                else:
                    remaining.append(t)
            state["tranches"] = remaining
            hour_gap = 0
            for _, flow in sorted(movements, key=lambda m: (m[0], m[1] >= 0)):
                state["cash"] = round(state["cash"] + flow, 2)
                gap = max(0, DEFAULT_POLICY["minimum_buffer"] - state["cash"])
                if gap:
                    breaches += 1
                    total_gap += gap
                    max_gap = max(max_gap, gap)
                    hour_gap = max(hour_gap, gap)
            # Illustrative one-hour financing charge on peak hourly floor gap.
            # Funding is measured, never silently injected into cash.
            borrowing += hour_gap * borrowing_rate / 100 / 8760
            state["history"].append(copy.deepcopy(actual))
        results.append(
            {
                "strategy": strategy,
                "realized_interest": round(interest, 2),
                "accrued_interest": round(accrued, 2),
                "fees": round(fees, 2),
                "penalties": 0,
                "borrowing_cost": round(borrowing, 2),
                "net_interest": round(accrued - fees - borrowing, 2),
                "average_idle_cash": round(idle / hours, 2),
                "floor_breaches": breaches,
                "total_shortfall": round(total_gap, 2),
                "maximum_shortfall": round(max_gap, 2),
                "surplus_utilization": invested / eligible_total
                if eligible_total
                else 0,
                "successful_sweeps": successes,
                "failed_sweeps": failed,
                "recoveries": recovered,
                "forecast_mae": float(np.mean(np.abs(errors))),
                "forecast_rmse": float(np.sqrt(np.mean(np.square(errors)))),
            }
        )
    return {
        "mode": "simulation",
        "source": source,
        "hours": hours,
        "model": model,
        "initial_cash": 100_000_000,
        "fixed_buffer": fixed_buffer,
        "borrowing_rate": borrowing_rate,
        "failure_every": failure_every,
        "test_start": history[start]["timestamp"],
        "test_end": history[-1]["timestamp"],
        "results": results,
        "assumptions": [
            "Hourly rolling origins; all strategies see identical prefixes "
            "and gross flows.",
            "No scheduled external obligations in this historical CSV "
            "comparison; stress scenarios are separate.",
            "Net interest uses accrual less entry fees and modeled borrowing "
            "costs; realized interest is separate.",
            "Shortfalls count each below-floor observation, not distinct "
            "missed payments; total may include repeated deficits.",
            "C maximizes net return per placement across three products, not "
            "a global multi-period portfolio optimum.",
            "Peak hourly floor gaps incur one hour of illustrative financing "
            "cost; no financing is actually advanced.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--model", choices=["fallback", "sarimax"], default="fallback")
    parser.add_argument("--failure-every", type=int, default=0)
    parser.add_argument("--output", default=".runtime/strategy-comparison.json")
    args = parser.parse_args()
    report = compare_strategies(
        hours=args.hours, model=args.model, failure_every=args.failure_every
    )
    report["source"] = "seed-42 synthetic INR hourly cashflows"
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
