from datetime import timedelta

import pytest

from liquidity_forecasting.planning import (
    analyze,
    apply_planning,
    evaluate,
    iso,
    moment,
    timeline,
)
from liquidity_forecasting.treasury import initial_state


def test_ten_million_example_never_spends_three_pm_deposit_at_two_pm():
    now = moment("2026-10-18T12:00:00Z")
    transactions = [
        {"timestamp": "2026-10-18T14:00:00Z", "flow": -7_000_000},
        {"timestamp": "2026-10-18T15:00:00Z", "flow": 4_000_000},
    ]
    plan = evaluate(10_000_000, transactions, 1_000_000, 24, 5, 0, 1, now)
    assert plan["required"] == 8_000_000
    assert plan["suggested"] == 2_000_000
    assert 10_000_000 - plan["suggested"] - 7_000_000 == 1_000_000


def test_earlier_maturity_can_release_more_principal():
    now = moment("2026-10-18T12:00:00Z")
    rows = [{"timestamp": iso(now + timedelta(hours=8)), "flow": -7_000_000}]
    short = evaluate(10_000_000, rows, 1_000_000, 6, 4, 0, 1, now)
    long = evaluate(10_000_000, rows, 1_000_000, 24, 5, 0, 1, now)
    assert short["suggested"] == 9_000_000
    assert long["suggested"] == 2_000_000


def test_fee_can_never_create_a_later_shortfall():
    now = moment("2026-10-18T12:00:00Z")
    rows = [{"timestamp": iso(now + timedelta(hours=48)), "flow": -9_000_000}]
    plan = evaluate(10_000_000, rows, 1_000_000, 6, 5, 20, 1, now)
    assert plan["suggested"] == 0


def test_yield_uses_duration_and_fee_and_minimum():
    now = moment("2026-10-18T12:00:00Z")
    plan = evaluate(10_000_000, [], 1_000_000, 6, 4, 20, 250_000, now)
    assert plan["interest"] == round(plan["suggested"] * 0.04 * 6 / (365 * 24), 2)
    assert plan["net_return"] == round(plan["interest"] - 20, 2)
    rejected = evaluate(100_000, [], 50_000, 6, 4, 20, 250_000, now)
    assert rejected["suggested"] == 0


def test_default_all_recommended_options_preserve_floor_at_every_time():
    state = initial_state()
    plan = analyze(state)
    now = moment(state["history"][-1]["timestamp"])
    for option in plan["options"]:
        if not option["suggested"]:
            continue
        balance = state["cash"] - option["suggested"] - option["fee"]
        redeemed = False
        for transaction in plan["timeline"]:
            if (
                moment(transaction["timestamp"])
                > now + timedelta(hours=option["hours"])
                and not redeemed
            ):
                balance += option["suggested"] + option["interest"]
                redeemed = True
            balance += transaction["flow"]
            assert balance >= plan["floor"] - 0.01


def test_combined_stress_reduces_surplus_without_mutating_baseline():
    state = initial_state()
    baseline = analyze(state)
    stressed = analyze(state, {"withdrawals": 50, "delay": 12, "payout": 10_000_000})
    assert stressed["selected"]["shortfall"] > baseline["selected"]["shortfall"]
    assert stressed["selected"]["suggested"] == 0
    assert analyze(state) == baseline


def test_merchant_reclassification_is_not_double_counted():
    state = initial_state()
    state["scheduled"] = []
    rows = timeline(state)
    total = sum(t["flow"] for t in rows)
    mean_daily_net = (
        sum(r["deposits"] - r["withdrawals"] for r in state["history"][-336:]) / 14
    )
    assert total == pytest.approx(mean_daily_net * 3, abs=1)


def test_event_delay_changes_timestamp_and_records_explanation():
    state = initial_state()
    before = analyze(state)
    apply_planning(state, "planning_event", {"kind": "delay", "hours": 12})
    after = analyze(state)
    original = next(e for e in before["events"] if e["kind"] == "settlement")
    delayed = next(e for e in after["events"] if e["kind"] == "settlement")
    assert moment(delayed["timestamp"]) - moment(original["timestamp"]) == timedelta(
        hours=12
    )
    assert state["decisions"][0]["before"] == before["selected"]
    assert "changed reserve" in state["decisions"][0]["reason"]


def test_investment_charges_fee_and_creates_locked_tranche():
    state = initial_state()
    chosen = analyze(state)["selected"]
    assert chosen["suggested"] > 0
    apply_planning(state, "planning_invest", {})
    assert state["cash"] == round(100_000_000 - chosen["suggested"] - chosen["fee"], 2)
    assert state["vault"] == 250_000_000 + chosen["suggested"]
    assert state["tranches"][0]["matures"] == chosen["matures"]
    assert analyze(state)["selected"]["suggested"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"withdrawals": -1},
        {"withdrawals": float("inf")},
        {"delay": 49},
        {"payout": "5000"},
        {"withdrawals": True},
    ],
)
def test_invalid_stress_rejected(payload):
    with pytest.raises(ValueError):
        analyze(initial_state(), payload)
