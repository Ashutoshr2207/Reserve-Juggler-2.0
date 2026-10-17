from typing import Optional, Sequence

import numpy as np
import pandas as pd

DEFAULT_CURRENCIES = ("EUR", "USD", "JPY", "BRL", "INR", "AUD")

CURRENCY_SCALES = {
    "EUR": 1.00,
    "USD": 1.10,
    "JPY": 150.00,
    "BRL": 5.50,
    "INR": 90.00,
    "AUD": 1.65,
}


def generate_sample_cashflows(
    start: str = "2022-01-01",
    end: str = "2025-01-01",
    currencies: Optional[Sequence[str]] = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic synthetic daily net cashflows by currency."""
    selected_currencies = (
        list(currencies) if currencies is not None else list(DEFAULT_CURRENCIES)
    )

    dates = pd.date_range(start=start, end=end, freq="D")
    random_generator = np.random.default_rng(seed)

    data = {}

    for currency in selected_currencies:
        scale = CURRENCY_SCALES.get(currency, 1.0)

        regular_activity = random_generator.normal(
            loc=500 * scale,
            scale=2_000 * scale,
            size=len(dates),
        )

        weekly_receipts = np.where(
            dates.dayofweek == 0,
            6_000 * scale,
            0,
        )

        payroll = np.where(
            dates.day == 25,
            18_000 * scale,
            0,
        )

        month_end_payments = np.where(
            dates.is_month_end,
            9_000 * scale,
            0,
        )

        shock_events = random_generator.random(len(dates)) < 0.01
        shock_costs = np.where(
            shock_events,
            random_generator.uniform(
                8_000 * scale,
                20_000 * scale,
                size=len(dates),
            ),
            0,
        )

        data[currency] = (
            regular_activity
            + weekly_receipts
            - payroll
            - month_end_payments
            - shock_costs
        )

    cashflows = pd.DataFrame(data, index=dates)
    cashflows.index.name = "Date"

    return cashflows


def load_cashflow_data(
    start: str = "2022-01-01",
    end: str = "2025-01-01",
    currencies: Optional[Sequence[str]] = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Return sample data while preserving the original public function."""
    return generate_sample_cashflows(
        start=start,
        end=end,
        currencies=currencies,
        seed=seed,
    )


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill missing observations."""
    return df.ffill()
