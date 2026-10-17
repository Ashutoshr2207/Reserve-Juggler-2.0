from typing import Mapping

import pandas as pd

DEFAULT_OPENING_BALANCES = {
    "EUR": 250_000.0,
    "USD": 275_000.0,
    "JPY": 37_500_000.0,
    "BRL": 1_375_000.0,
    "INR": 22_500_000.0,
    "AUD": 412_500.0,
}

DEFAULT_MINIMUM_BUFFERS = {
    "EUR": 50_000.0,
    "USD": 55_000.0,
    "JPY": 7_500_000.0,
    "BRL": 275_000.0,
    "INR": 4_500_000.0,
    "AUD": 82_500.0,
}


def project_balances(
    opening_balances: Mapping[str, float],
    forecast_cashflows: Mapping[str, pd.Series],
) -> pd.DataFrame:
    """Calculate future balances from opening balances and net cashflows."""
    if not forecast_cashflows:
        raise ValueError("At least one cashflow forecast is required.")

    projected = {}
    expected_index = None

    for currency, cashflows in forecast_cashflows.items():
        if currency not in opening_balances:
            raise ValueError(f"Opening balance is missing for currency '{currency}'.")

        cashflow_series = pd.Series(cashflows, dtype=float)

        if cashflow_series.empty:
            raise ValueError(f"Cashflow forecast for '{currency}' cannot be empty.")

        if expected_index is None:
            expected_index = cashflow_series.index
        elif not cashflow_series.index.equals(expected_index):
            raise ValueError("All cashflow forecasts must use the same dates.")

        projected[currency] = (
            float(opening_balances[currency]) + cashflow_series.cumsum()
        )

    result = pd.DataFrame(projected)
    result.index.name = "Date"

    return result


def calculate_liquidity_shortfalls(
    projected_balances: pd.DataFrame,
    minimum_buffers: Mapping[str, float],
) -> pd.DataFrame:
    """Calculate funding needed to maintain each minimum balance."""
    if projected_balances.empty:
        raise ValueError("Projected balances cannot be empty.")

    missing_currencies = [
        currency
        for currency in projected_balances.columns
        if currency not in minimum_buffers
    ]

    if missing_currencies:
        missing = ", ".join(missing_currencies)
        raise ValueError(f"Minimum buffers are missing for: {missing}.")

    shortfalls = {}

    for currency in projected_balances.columns:
        minimum_buffer = float(minimum_buffers[currency])

        if minimum_buffer < 0:
            raise ValueError(f"Minimum buffer for '{currency}' cannot be negative.")

        shortfalls[currency] = (minimum_buffer - projected_balances[currency]).clip(
            lower=0
        )

    result = pd.DataFrame(shortfalls)
    result.index.name = projected_balances.index.name

    return result
