from typing import Dict, Mapping

import numpy as np
import pandas as pd
from scipy.optimize import linprog

DEFAULT_TRANSFER_COST_RATES = {
    "EUR": 0.0005,
    "USD": 0.0010,
    "JPY": 0.0015,
    "BRL": 0.0030,
    "INR": 0.0025,
    "AUD": 0.0012,
}

DEFAULT_PRIORITY_WEIGHTS = {
    "EUR": 1.0,
    "USD": 1.0,
    "JPY": 1.0,
    "BRL": 1.0,
    "INR": 1.0,
    "AUD": 1.0,
}


def optimize_allocation(forecasts: Dict[str, pd.Series]) -> Dict[str, float]:
    """
    Compute a simple allocation based on total absolute forecasted cashflows.

    Parameters
    ----------
    forecasts : dict
        Mapping from currency code to forecast series/array.

    Returns
    -------
    dict
        Mapping from currency code to allocation weight (summing to 1.0).
    """
    totals = {}
    for ccy, fc in forecasts.items():
        # Convert to Series for consistent handling
        s = pd.Series(fc)
        totals[ccy] = float(np.abs(s).sum())

    grand_total = sum(totals.values())
    if grand_total == 0:
        # Edge case: if everything is zero, allocate equally
        n = len(totals)
        return {ccy: 1.0 / n for ccy in totals}

    allocations = {ccy: total / grand_total for ccy, total in totals.items()}
    return allocations


def allocate_funds_by_shortfall(
    shortfalls_in_base_currency: Mapping[str, float],
    available_funds: float,
) -> Dict[str, float]:
    """Allocate available funds proportionally to liquidity shortfalls."""
    if not shortfalls_in_base_currency:
        raise ValueError("At least one liquidity shortfall is required.")

    if available_funds < 0:
        raise ValueError("Available funds cannot be negative.")

    normalized_shortfalls = {
        currency: float(shortfall)
        for currency, shortfall in shortfalls_in_base_currency.items()
    }

    negative_currencies = [
        currency
        for currency, shortfall in normalized_shortfalls.items()
        if shortfall < 0
    ]

    if negative_currencies:
        invalid = ", ".join(negative_currencies)
        raise ValueError(f"Liquidity shortfalls cannot be negative for: {invalid}.")

    total_shortfall = sum(normalized_shortfalls.values())

    if total_shortfall == 0 or available_funds == 0:
        return {currency: 0.0 for currency in normalized_shortfalls}

    funding_ratio = min(
        1.0,
        float(available_funds) / total_shortfall,
    )

    return {
        currency: shortfall * funding_ratio
        for currency, shortfall in normalized_shortfalls.items()
    }


def optimize_funding_allocation(
    shortfalls_in_base_currency: Mapping[str, float],
    available_funds: float,
    transfer_cost_rates: Mapping[str, float],
    priority_weights: Mapping[str, float] = None,
) -> Dict[str, float]:
    """Optimize funding under budget, shortfall, cost, and priority constraints."""
    if not shortfalls_in_base_currency:
        raise ValueError("At least one liquidity shortfall is required.")

    if available_funds < 0:
        raise ValueError("Available funds cannot be negative.")

    currencies = list(shortfalls_in_base_currency)

    missing_costs = [
        currency for currency in currencies if currency not in transfer_cost_rates
    ]
    if missing_costs:
        missing = ", ".join(missing_costs)
        raise ValueError(f"Transfer costs are missing for: {missing}.")

    shortfalls = [
        float(shortfalls_in_base_currency[currency]) for currency in currencies
    ]
    costs = [float(transfer_cost_rates[currency]) for currency in currencies]

    if any(shortfall < 0 for shortfall in shortfalls):
        raise ValueError("Liquidity shortfalls cannot be negative.")

    if any(cost < 0 for cost in costs):
        raise ValueError("Transfer cost rates cannot be negative.")

    if priority_weights is None:
        priorities = [1.0 for _ in currencies]
    else:
        missing_priorities = [
            currency for currency in currencies if currency not in priority_weights
        ]
        if missing_priorities:
            missing = ", ".join(missing_priorities)
            raise ValueError(f"Priority weights are missing for: {missing}.")

        priorities = [float(priority_weights[currency]) for currency in currencies]

    if any(priority <= 0 for priority in priorities):
        raise ValueError("Priority weights must be positive.")

    if available_funds == 0 or sum(shortfalls) == 0:
        return {currency: 0.0 for currency in currencies}

    objective = [cost - priority for cost, priority in zip(costs, priorities)]

    result = linprog(
        c=objective,
        A_ub=[[1.0] * len(currencies)],
        b_ub=[float(available_funds)],
        bounds=[(0.0, shortfall) for shortfall in shortfalls],
        method="highs",
    )

    if not result.success:
        raise RuntimeError(f"Funding optimization failed: {result.message}")

    return {currency: float(amount) for currency, amount in zip(currencies, result.x)}
