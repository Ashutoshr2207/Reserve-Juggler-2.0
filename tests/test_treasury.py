import copy
import json

import pandas as pd
import pytest

import liquidity_forecasting.treasury as treasury
from liquidity_forecasting.model import seasonal_naive_fallback


def rows(amount=-100, periods=72):
    dates = pd.date_range("2026-10-18 09:00", periods=periods, freq="h")
    return [
        {
            "timestamp": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mean": amount,
            "lower": amount - 50,
            "upper": amount + 50,
            "withdrawals": 1_000,
        }
        for date in dates
    ]


@pytest.fixture
def state(monkeypatch):
    monkeypatch.setattr(treasury, "forecast", lambda state: (rows(), "Test", True, 10))
    return treasury.initial_state()


def test_reserve_protects_every_hour_not_just_terminal_balance():
    forecast = rows(0, 3)
    for row, value in zip(forecast, [-1000, 2000, -100]):
        row["lower"] = value
    policy = dict(treasury.DEFAULT_POLICY, minimum_buffer=500, lock_hours=3)
    plan = treasury.reserve_plan(5000, forecast, policy)
    assert plan["required"] == 1500
    assert plan["sweep"] == 3500
    cash = 5000 - plan["sweep"]
    for row in forecast:
        cash += row["lower"]
        assert cash >= 500


def test_stress_increases_required_reserve_and_blocks_surplus():
    policy = dict(treasury.DEFAULT_POLICY, minimum_buffer=500, lock_hours=24)
    normal = treasury.reserve_plan(5000, rows(), policy)
    stressed = treasury.reserve_plan(5000, rows(), dict(policy, withdrawal_stress=50))
    assert stressed["required"] > normal["required"]
    assert stressed["sweep"] == 0
    assert stressed["shortfall"] > 0


def test_positive_flows_do_not_reduce_minimum_buffer():
    policy = dict(treasury.DEFAULT_POLICY, minimum_buffer=500)
    plan = treasury.reserve_plan(1000, rows(100), policy)
    assert plan["required"] == 500
    assert plan["sweep"] == 500


def test_sweep_conserves_principal_and_rejects_duplicate_revision(state):
    result = treasury.apply_action(state, "sweep", {"revision": 0})
    assert result["cash"] + result["vault"] == state["cash"] + state["vault"]
    assert (
        result["cash"]
        >= treasury.reserve_plan(state["cash"], rows(), state["policy"])["required"]
    )
    assert result["tranches"][0]["amount"] > 0
    assert result["ledger"][0]["type"] == "Sweep"
    assert state["ledger"] == []  # Transactional copy, no partial side effects.
    with pytest.raises(ValueError, match="workspace changed"):
        treasury.apply_action(result, "sweep", {"revision": 0})
    with pytest.raises(ValueError, match="No eligible surplus"):
        treasury.apply_action(result, "sweep", {"revision": 1})


def test_maturity_returns_principal_and_interest_at_original_rate(state):
    state["policy"]["lock_hours"] = 1
    swept = treasury.apply_action(state, "sweep", {"revision": 0})
    principal = swept["tranches"][0]["amount"]
    swept["policy"]["annual_yield"] = 10
    result = treasury.apply_action(swept, "advance", {"revision": 1})
    interest = round(principal * 0.05 / (365 * 24), 2)
    assert result["tranches"] == []
    assert result["vault"] == state["vault"]
    assert result["earned"] == interest
    net = next(r["amount"] for r in result["ledger"] if r["type"] == "Cashflow")
    assert result["cash"] == pytest.approx(state["cash"] + net + interest)


def test_locked_principal_cannot_be_used_early(state):
    swept = treasury.apply_action(state, "sweep", {"revision": 0})
    result = treasury.apply_action(swept, "advance", {"revision": 1})
    assert result["tranches"] == swept["tranches"]
    assert result["vault"] == swept["vault"]
    assert result["earned"] == 0


def test_auto_sweep_runs_after_simulated_hour(state):
    state["policy"]["auto_sweep"] = True
    result = treasury.apply_action(state, "advance", {"revision": 0})
    assert any(r["type"] == "Sweep" for r in result["ledger"])


def test_shortfall_stops_automation_without_inventing_emergency_funding(
    state, monkeypatch
):
    stressed_rows = rows()
    for row in stressed_rows:
        row["withdrawals"] = 2_000_000
    monkeypatch.setattr(
        treasury, "forecast", lambda state: (stressed_rows, "Test", True, 10)
    )
    state["cash"] = 0
    state["policy"].update(auto_sweep=True, withdrawal_stress=100)
    result = treasury.apply_action(state, "advance", {"revision": 0})
    assert result["cash"] < 0
    assert not result["policy"]["auto_sweep"]
    assert any(r["type"] == "Shortfall" for r in result["ledger"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("minimum_buffer", -1),
        ("minimum_buffer", float("inf")),
        ("annual_yield", float("nan")),
        ("lock_hours", 0),
        ("lock_hours", 1.5),
        ("confidence", 91),
        ("withdrawal_stress", 101),
        ("auto_sweep", "false"),
        ("minimum_buffer", True),
        ("annual_yield", "5"),
    ],
)
def test_policy_rejects_invalid_values(field, value):
    policy = dict(treasury.DEFAULT_POLICY, **{field: value})
    with pytest.raises(ValueError):
        treasury.validate_policy(policy)


def test_csv_roundtrip_and_strict_rejections():
    history = treasury.sample_history()[:168]
    assert treasury.parse_csv(pd.DataFrame(history).to_csv(index=False)) == history
    for change in ["duplicate", "gap", "negative", "infinite", "missing"]:
        bad = copy.deepcopy(history)
        if change == "duplicate":
            bad[1]["timestamp"] = bad[0]["timestamp"]
        elif change == "gap":
            bad.pop(1)
        elif change == "negative":
            bad[0]["deposits"] = -1
        elif change == "infinite":
            bad[0]["withdrawals"] = float("inf")
        else:
            bad[0]["withdrawals"] = None
        with pytest.raises(ValueError):
            treasury.validate_history(bad)


def test_import_disables_automation_and_preserves_balances(state):
    state["policy"]["auto_sweep"] = True
    result = treasury.apply_action(
        state,
        "import",
        {"revision": 0, "csv": pd.DataFrame(state["history"]).to_csv(index=False)},
    )
    assert result["cash"] == state["cash"]
    assert not result["policy"]["auto_sweep"]
    assert "Imported" in result["source"]


def test_import_is_blocked_while_tranches_are_locked(state):
    swept = treasury.apply_action(state, "sweep", {"revision": 0})
    with pytest.raises(ValueError, match="Reset the sandbox"):
        treasury.apply_action(swept, "import", {"revision": 1, "csv": "invalid"})


def test_hourly_fallback_keeps_hourly_dates():
    frame = pd.DataFrame(treasury.sample_history()[:168])
    series = pd.Series(frame.deposits.to_numpy(), index=pd.to_datetime(frame.timestamp))
    result = seasonal_naive_fallback(series, 4, season_length=24, frequency="h")
    assert result.mean.index[0] - series.index[-1] == pd.Timedelta(hours=1)
    assert result.mean.index[1] - result.mean.index[0] == pd.Timedelta(hours=1)


def test_real_hourly_forecast_produces_finite_serializable_snapshot():
    result = treasury.snapshot(treasury.initial_state())
    assert len(result["forecast"]) == 72
    assert pd.Timestamp(result["forecast"][0]["timestamp"]) - pd.Timestamp(
        result["as_of"]
    ) == pd.Timedelta(hours=1)
    assert result["plan"]["required"] >= result["policy"]["minimum_buffer"]
    assert result["model"] in ("SARIMAX", "Seasonal Naive (fallback)")
    json.dumps(result, allow_nan=False)
