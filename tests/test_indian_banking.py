import copy
from datetime import timedelta

import pandas as pd
import pytest

from liquidity_forecasting.planning import (
    analyze,
    apply_planning,
    evaluate,
    inr,
    moment,
    timeline,
)
from liquidity_forecasting.treasury import initial_state, validate_history
from server import Store


def test_ten_crore_protects_two_pm_payment_before_three_pm_ist_settlement():
    transactions = [
        {"timestamp": "2026-10-18T14:00:00+05:30", "flow": -70_000_000},
        {"timestamp": "2026-10-18T15:00:00+05:30", "flow": 40_000_000},
    ]
    plan = evaluate(
        100_000_000,
        transactions,
        10_000_000,
        24,
        5,
        0,
        1,
        moment("2026-10-18T12:00:00+05:30"),
    )
    assert plan["required"] == 80_000_000
    assert plan["suggested"] == 20_000_000
    assert 100_000_000 - plan["suggested"] - 70_000_000 == 10_000_000
    assert moment(transactions[1]["timestamp"]) - moment(
        transactions[0]["timestamp"]
    ) == timedelta(hours=1)


def test_indian_currency_groups_lakhs_and_crores():
    assert inr(100_000_000) == "₹10,00,00,000.00"
    assert inr(250_000) == "₹2,50,000.00"
    assert inr(-50.25) == "−₹50.25"


def test_all_payment_channels_and_upi_specific_stress():
    state = initial_state()
    baseline = timeline(state)
    stressed = timeline(state, {"upi": 50})
    assert {"UPI", "IMPS", "NEFT", "RTGS", "ATM"} <= {r["kind"] for r in baseline}
    for kind in ("IMPS", "NEFT", "RTGS", "ATM", "deposit", "settlement"):
        assert [r for r in baseline if r["kind"] == kind] == [
            r for r in stressed if r["kind"] == kind
        ]
    upi = sum(r["flow"] for r in baseline if r["kind"] == "UPI")
    stressed_upi = sum(r["flow"] for r in stressed if r["kind"] == "UPI")
    assert stressed_upi == pytest.approx(upi * 1.5, abs=1)


def test_ist_csv_roundtrip_and_ambiguous_timezone_rejected():
    state = initial_state()
    records = copy.deepcopy(state["history"][:168])
    for row in records:
        row["timestamp"] = (
            pd.Timestamp(row["timestamp"]).tz_convert("Asia/Kolkata").isoformat()
        )
    assert validate_history(records) == state["history"][:168]
    records[0]["timestamp"] = "2026-09-01T10:00:00"
    with pytest.raises(ValueError, match="timezone"):
        validate_history(records)


def test_ist_on_hour_history_is_valid():
    records = [
        {"timestamp": date.isoformat(), "deposits": 1e7, "withdrawals": 9e6}
        for date in pd.date_range("2026-10-01T00:00:00+05:30", periods=168, freq="h")
    ]
    normalized = validate_history(records)
    assert normalized[0]["timestamp"] == "2026-09-30T18:30:00Z"


def test_demo_rates_balances_and_return_calculation_are_persistent(tmp_path):
    state = initial_state()
    apply_planning(
        state,
        "planning_policy",
        {"option": "overnight", "risk_buffer": 5_000_000, "rates": {"overnight": 7.25}},
    )
    chosen = analyze(state)["selected"]
    assert chosen["rate"] == 7.25
    assert chosen["interest"] == round(chosen["suggested"] * 0.0725 / 365, 2)
    apply_planning(
        state, "planning_balance", {"cash": 200_000_000, "vault": 300_000_000}
    )
    store = Store(tmp_path / "inr.sqlite3")
    store.write("inr", state)
    restored = store.read("inr")
    assert restored["cash"] == 200_000_000
    assert analyze(restored)["selected"]["rate"] == 7.25
    store.connection.close()


def test_usd_demo_is_archived_instead_of_converted(tmp_path):
    store = Store(tmp_path / "migration.sqlite3")
    original = initial_state()
    original.pop("currency")
    original["cash"] = 12345
    store.write("old", original)
    migrated = store.read("old")
    assert migrated["currency"] == "INR"
    assert migrated["cash"] == 100_000_000
    row = store.connection.execute(
        "SELECT state FROM workspaces WHERE id=?", ("old:legacy-usd",)
    ).fetchone()
    assert "12345" in row[0]
    assert "no currency conversion" in migrated["migration_note"]
    store.connection.close()


def test_upi_festival_combination_rejects_unfunded_investment():
    state = initial_state()
    stressed = analyze(
        state, {"upi": 70, "withdrawals": 15, "delay": 6, "payout": 30_000_000}
    )
    assert stressed["selected"]["risk"] == "High Risk"
    assert stressed["selected"]["suggested"] == 0


def test_demo_balance_edits_blocked_while_investments_locked():
    state = initial_state()
    apply_planning(state, "planning_invest", {})
    with pytest.raises(ValueError, match="locked"):
        apply_planning(state, "planning_balance", {"cash": 1e8, "vault": 2e8})
