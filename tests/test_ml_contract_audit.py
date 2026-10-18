"""Synthetic ordering regressions supporting the ML integration contract audit."""

from datetime import timedelta

import pytest

import liquidity_forecasting.treasury as treasury
from liquidity_forecasting.planning import analyze, iso, moment


@pytest.mark.parametrize("maturity_minutes", [-15, 0, 15])
def test_hour_17_payment_cannot_use_same_time_or_later_maturity(
    monkeypatch, maturity_minutes
):
    state = treasury.initial_state()
    for row in state["history"]:
        row.update(deposits=0, withdrawals=0)
    origin = moment(state["history"][-1]["timestamp"])
    due = origin + timedelta(hours=17)
    state.update(cash=15_000_000, vault=50_000_000)
    state["scheduled"] = [
        {
            "id": "hour-17-payment",
            "kind": "payment",
            "amount": 50_000_000,
            "timestamp": iso(due),
            "label": "Synthetic hour-17 regression payment",
        }
    ]
    state["tranches"] = [
        {
            "amount": 50_000_000,
            "annual_yield": 0,
            "hours": 24,
            "matures": iso(due + timedelta(minutes=maturity_minutes)),
        }
    ]

    def zero_forecast(current):
        now = moment(current["history"][-1]["timestamp"])
        rows = [
            {
                "timestamp": iso(now + timedelta(hours=h)),
                "mean": 0,
                "lower": 0,
                "upper": 0,
                "withdrawals": 0,
            }
            for h in range(1, 73)
        ]
        return rows, "Synthetic audit fixture", True, 0

    monkeypatch.setattr(treasury, "forecast", zero_forecast)
    assessment = analyze(state)["selected"]
    assert assessment["shortfall"] == (0 if maturity_minutes < 0 else 50_000_000)
    if maturity_minutes >= 0:
        assert assessment["suggested"] == 0

    for _ in range(17):
        state = treasury.apply_action(state, "advance", {"revision": state["revision"]})

    gaps = [e for e in state["ledger"] if e["type"] == "Shortfall"]
    assert bool(gaps) == (maturity_minutes >= 0)
    if gaps:
        assert any(moment(e["timestamp"]) == due for e in gaps)
    assert any(
        e["type"] == "Scheduled event" and moment(e["timestamp"]) == due
        for e in state["ledger"]
    )
    simulated_net = sum(e["amount"] for e in state["ledger"] if e["type"] == "Cashflow")
    expected = 15_000_000 if maturity_minutes <= 0 else -35_000_000
    assert state["cash"] == pytest.approx(expected + simulated_net, abs=0.01)


def test_hour_17_payment_cannot_use_hour_18_deposit():
    from liquidity_forecasting.planning import evaluate

    origin = moment("2026-10-18T00:00:00+05:30")
    assessment = evaluate(
        100_000_000,
        [
            {"timestamp": iso(origin + timedelta(hours=17)), "flow": -70_000_000},
            {"timestamp": iso(origin + timedelta(hours=18)), "flow": 40_000_000},
        ],
        floor=10_000_000,
        duration=24,
        rate=5,
        minimum=1,
        now=origin,
    )
    assert assessment["required"] == 80_000_000
    assert assessment["suggested"] == 20_000_000
    assert assessment["minimum_during_lock_after_sweep"] == 10_000_000
