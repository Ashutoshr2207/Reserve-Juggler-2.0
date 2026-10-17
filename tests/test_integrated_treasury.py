"""Acceptance tests for the integrated treasury workflow."""

import copy
from datetime import timedelta

import pytest

import liquidity_forecasting.treasury as treasury
from liquidity_forecasting.planning import analyze, iso, moment, timeline
from liquidity_forecasting.strategy_evaluation import (
    compare_strategies,
    evaluation_forecast,
)


@pytest.fixture
def state(monkeypatch):
    state = treasury.initial_state()
    rows = evaluation_forecast(state["history"])
    monkeypatch.setattr(treasury, "forecast", lambda state: (rows, "Test", True, 0))
    return state


def test_wider_forecast_uncertainty_reduces_allocation(state):
    rows = evaluation_forecast(state["history"])
    normal = analyze(state, forecast_rows=rows)
    for row in rows:
        row["lower"] -= 2_000_000
    uncertain = analyze(state, forecast_rows=rows)
    assert uncertain["selected"]["required"] > normal["selected"]["required"]
    assert uncertain["selected"]["suggested"] < normal["selected"]["suggested"]


def test_optimizer_selects_highest_eligible_net_income(state):
    plan = analyze(state)
    best = plan["optimized"]
    assert best["net_return"] == max(o["net_return"] for o in plan["options"])
    result = treasury.apply_action(state, "planning_optimize", {"revision": 0})
    assert result["cash"] == round(state["cash"] - best["suggested"] - best["fee"], 2)
    assert result["tranches"][0]["expected_interest"] == best["interest"]
    assert result["tranches"][0]["redemption"] == "No early redemption"


@pytest.mark.parametrize("outcome", ["failure", "timeout"])
def test_failed_execution_preserves_balances_and_records_deferral(state, outcome):
    result = treasury.apply_action(
        state,
        "planning_optimize",
        {"revision": 0, "execution": outcome, "request_id": "fail-once"},
    )
    assert (result["cash"], result["vault"], result["tranches"]) == (
        state["cash"],
        state["vault"],
        [],
    )
    assert result["ledger"][0]["type"] == "Failed sweep"
    assert "Deferred" in result["decisions"][0]["reason"]
    assert (
        treasury.apply_action(
            result,
            "planning_optimize",
            {"revision": 0, "execution": outcome, "request_id": "fail-once"},
        )
        == result
    )


def test_exact_retry_is_idempotent_even_after_other_updates(state):
    payload = {"revision": 0, "request_id": "placement-1"}
    placed = treasury.apply_action(state, "planning_optimize", payload)
    updated = treasury.apply_action(
        placed,
        "planning_event",
        {"revision": 1, "kind": "deposit", "amount": 1000, "hours": 2},
    )
    assert treasury.apply_action(updated, "planning_optimize", payload) == updated
    with pytest.raises(ValueError, match="different payload"):
        treasury.apply_action(
            updated, "planning_optimize", dict(payload, execution="failure")
        )


def test_intrahour_maturity_covers_later_obligation_but_not_earlier(state):
    now = moment(state["history"][-1]["timestamp"])
    state["cash"] = 15_000_000
    state["vault"] = 100_000_000
    state["tranches"] = [
        {
            "amount": 100_000_000,
            "annual_yield": 5,
            "hours": 6,
            "matures": iso(now + timedelta(minutes=30)),
        }
    ]

    def scenario(minutes):
        test_state = copy.deepcopy(state)
        test_state["scheduled"] = [
            {
                "id": "large",
                "kind": "payment",
                "amount": 50_000_000,
                "timestamp": iso(now + timedelta(minutes=minutes)),
                "label": "Intrahour obligation",
            }
        ]
        return treasury.apply_action(test_state, "advance", {"revision": 0})

    early = scenario(15)
    late = scenario(45)
    assert any(e["type"] == "Shortfall" for e in early["ledger"])
    assert not any(e["type"] == "Shortfall" for e in late["ledger"])
    assert early["cash"] == late["cash"]  # Same end balance hides earlier breach.


def test_same_time_payment_precedes_maturity(state):
    now = moment(state["history"][-1]["timestamp"])
    state["cash"] = 15_000_000
    state["tranches"] = [
        {
            "amount": 100_000_000,
            "annual_yield": 5,
            "hours": 6,
            "matures": iso(now + timedelta(minutes=30)),
        }
    ]
    state["scheduled"] = [
        {
            "id": "large",
            "kind": "payment",
            "amount": 50_000_000,
            "timestamp": state["tranches"][0]["matures"],
            "label": "Due at maturity",
        }
    ]
    result = treasury.apply_action(state, "advance", {"revision": 0})
    assert any(e["type"] == "Shortfall" for e in result["ledger"])


def test_reconciliation_rejects_impossible_locked_principal(state):
    state["vault"] = 1
    state["tranches"] = [
        {
            "amount": 1000,
            "annual_yield": 5,
            "hours": 24,
            "matures": "2026-10-19T08:00:00Z",
        }
    ]
    with pytest.raises(ValueError, match="Reconciliation"):
        treasury.apply_action(
            state, "policy", {"revision": 0, "policy": state["policy"]}
        )


def test_timezones_required():
    with pytest.raises(ValueError, match="timezone"):
        moment("2026-10-18T12:00:00")


def test_uncertainty_is_not_a_second_copy_of_net_cashflows(state):
    state["scheduled"] = []
    rows = evaluation_forecast(state["history"])
    for row in rows:
        row["lower"] = row["mean"]
    transactions = timeline(state, forecast_rows=rows)
    assert sum(t["flow"] for t in transactions) == pytest.approx(
        sum(r["mean"] for r in rows), abs=1
    )


def test_backtest_only_passes_training_prefix_and_does_not_mutate_history():
    history = treasury.sample_history()[:192]
    original = copy.deepcopy(history)
    cutoffs = []

    def predictor(prefix):
        cutoffs.append(prefix[-1]["timestamp"])
        return evaluation_forecast(prefix)

    report = compare_strategies(history, hours=4, predictor=predictor)
    assert cutoffs == [r["timestamp"] for r in history[187:191]]
    assert history == original
    assert len(report["results"]) == 3
    assert len({r["forecast_mae"] for r in report["results"]}) == 1


def test_future_changes_cannot_change_earlier_predictions():
    history = treasury.sample_history()[:192]
    earlier = evaluation_forecast(history[:180])
    for row in history[180:]:
        row["withdrawals"] *= 10
    assert evaluation_forecast(history[:180]) == earlier


def test_failure_replay_reports_failures_and_recoveries():
    report = compare_strategies(hours=24, failure_every=2)
    assert all(r["failed_sweeps"] > 0 for r in report["results"])
    assert all(r["recoveries"] > 0 for r in report["results"])


def test_risk_alert_immediately_changes_reserve(state):
    before = analyze(state)
    result = treasury.apply_action(
        state,
        "planning_event",
        {"revision": 0, "kind": "risk", "amount": 20_000_000, "hours": 1},
    )
    assert analyze(result)["selected"]["required"] > before["selected"]["required"]
    assert result["cash"] == state["cash"]


def test_failure_scenario_keeps_saved_state_unchanged(state):
    before = copy.deepcopy(state)
    result = analyze(state, {"execution": "failure"})
    assert all(o["suggested"] == 0 for o in result["options"])
    assert result["selected"]["net_return"] == 0
    assert state == before


def test_extreme_negative_forecast_reconciles_without_invented_cash(state):
    state["scheduled"] = []
    rows = evaluation_forecast(state["history"])
    for row in rows:
        row["mean"] = row["lower"] = -50_000_000
    flows = timeline(state, forecast_rows=rows)
    assert sum(t["flow"] for t in flows) == pytest.approx(-50_000_000 * 72, abs=1)
    assert analyze(state, forecast_rows=rows)["optimized"]["suggested"] == 0


def test_gross_forecasts_are_separate_nonnegative_and_time_aligned(state):
    result = treasury.gross_forecast(state)
    assert len(result["rows"]) == 72
    first = result["rows"][0]
    assert first["deposits"] == state["history"][-24]["deposits"]
    assert first["withdrawals"] == state["history"][-24]["withdrawals"]
    assert moment(first["timestamp"]) > moment(state["history"][-1]["timestamp"])


def test_ingestion_rejects_boolean_amounts():
    history = treasury.sample_history()[:168]
    history[0]["deposits"] = True
    with pytest.raises(ValueError, match="booleans"):
        treasury.validate_history(history)


def test_failure_scenario_does_not_hide_underlying_funding_gap(state):
    result = analyze(state, {"execution": "failure", "withdrawals": 50})
    assert result["selected"]["shortfall"] > 0
    assert result["selected"]["risk"] == "High Risk"
