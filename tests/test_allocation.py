import pytest

from liquidity_forecasting.allocation import (
    allocate_funds_by_shortfall,
    optimize_funding_allocation,
)


def test_allocate_all_required_funding_when_funds_are_sufficient():
    result = allocate_funds_by_shortfall(
        {"EUR": 100.0, "USD": 50.0},
        available_funds=200.0,
    )

    assert result == {
        "EUR": 100.0,
        "USD": 50.0,
    }


def test_allocate_funds_proportionally_when_funds_are_limited():
    result = allocate_funds_by_shortfall(
        {"EUR": 100.0, "USD": 50.0},
        available_funds=60.0,
    )

    assert result["EUR"] == pytest.approx(40.0)
    assert result["USD"] == pytest.approx(20.0)


def test_allocate_zero_when_there_are_no_shortfalls():
    result = allocate_funds_by_shortfall(
        {"EUR": 0.0, "USD": 0.0},
        available_funds=100.0,
    )

    assert result == {
        "EUR": 0.0,
        "USD": 0.0,
    }


def test_reject_negative_available_funds():
    with pytest.raises(ValueError, match="cannot be negative"):
        allocate_funds_by_shortfall(
            {"EUR": 100.0},
            available_funds=-1.0,
        )


def test_reject_negative_shortfall():
    with pytest.raises(ValueError, match="cannot be negative"):
        allocate_funds_by_shortfall(
            {"EUR": -10.0},
            available_funds=100.0,
        )


def test_optimizer_covers_all_shortfalls_when_funds_are_sufficient():
    result = optimize_funding_allocation(
        {"EUR": 100.0, "USD": 50.0},
        available_funds=200.0,
        transfer_cost_rates={"EUR": 0.01, "USD": 0.02},
    )

    assert result["EUR"] == pytest.approx(100.0)
    assert result["USD"] == pytest.approx(50.0)


def test_optimizer_respects_available_funds():
    result = optimize_funding_allocation(
        {"EUR": 100.0, "USD": 100.0},
        available_funds=60.0,
        transfer_cost_rates={"EUR": 0.01, "USD": 0.02},
    )

    assert sum(result.values()) == pytest.approx(60.0)
    assert all(amount >= 0 for amount in result.values())


def test_optimizer_prefers_lower_transfer_cost():
    result = optimize_funding_allocation(
        {"EUR": 100.0, "USD": 100.0},
        available_funds=100.0,
        transfer_cost_rates={"EUR": 0.01, "USD": 0.02},
    )

    assert result["EUR"] == pytest.approx(100.0)
    assert result["USD"] == pytest.approx(0.0)


def test_optimizer_respects_priority_weights():
    result = optimize_funding_allocation(
        {"EUR": 100.0, "USD": 100.0},
        available_funds=100.0,
        transfer_cost_rates={"EUR": 0.01, "USD": 0.02},
        priority_weights={"EUR": 1.0, "USD": 2.0},
    )

    assert result["EUR"] == pytest.approx(0.0)
    assert result["USD"] == pytest.approx(100.0)
