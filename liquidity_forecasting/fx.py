from typing import Mapping

import pandas as pd

BASE_CURRENCY = "EUR"

DEFAULT_FX_TO_EUR = {
    "EUR": 1.0000,
    "USD": 0.9200,
    "JPY": 0.0062,
    "BRL": 0.1600,
    "INR": 0.0105,
    "AUD": 0.5600,
}


def convert_frame_to_base_currency(
    values: pd.DataFrame,
    fx_rates: Mapping[str, float],
) -> pd.DataFrame:
    """Convert currency columns into their base-currency equivalents."""
    if values.empty:
        raise ValueError("Currency values cannot be empty.")

    missing_currencies = [
        currency for currency in values.columns if currency not in fx_rates
    ]

    if missing_currencies:
        missing = ", ".join(missing_currencies)
        raise ValueError(f"FX rates are missing for: {missing}.")

    invalid_currencies = [
        currency for currency in values.columns if float(fx_rates[currency]) <= 0
    ]

    if invalid_currencies:
        invalid = ", ".join(invalid_currencies)
        raise ValueError(f"FX rates must be positive for: {invalid}.")

    rates = pd.Series(
        {currency: float(fx_rates[currency]) for currency in values.columns}
    )

    converted = values.mul(rates, axis="columns")
    converted.index.name = values.index.name

    return converted


def convert_amounts_to_base_currency(
    amounts: Mapping[str, float],
    fx_rates: Mapping[str, float],
) -> pd.Series:
    """Convert a currency-to-amount mapping into base currency."""
    if not amounts:
        raise ValueError("Currency amounts cannot be empty.")

    values = pd.DataFrame(
        [amounts],
        index=["Amount"],
    )

    converted = convert_frame_to_base_currency(
        values,
        fx_rates,
    )

    return converted.iloc[0]
