import pandas as pd
import pytest

from liquidity_forecasting.fx import (
    convert_amounts_to_base_currency,
    convert_frame_to_base_currency,
)


def test_convert_frame_to_base_currency():
    values = pd.DataFrame(
        {
            "EUR": [100.0, 200.0],
            "USD": [100.0, 200.0],
            "JPY": [1_000.0, 2_000.0],
        }
    )

    result = convert_frame_to_base_currency(
        values,
        {
            "EUR": 1.0,
            "USD": 0.9,
            "JPY": 0.006,
        },
    )

    expected = pd.DataFrame(
        {
            "EUR": [100.0, 200.0],
            "USD": [90.0, 180.0],
            "JPY": [6.0, 12.0],
        }
    )

    pd.testing.assert_frame_equal(result, expected)


def test_convert_amounts_to_base_currency():
    result = convert_amounts_to_base_currency(
        {"EUR": 100.0, "USD": 100.0},
        {"EUR": 1.0, "USD": 0.9},
    )

    expected = pd.Series(
        {"EUR": 100.0, "USD": 90.0},
        name="Amount",
    )

    pd.testing.assert_series_equal(result, expected)


def test_conversion_rejects_missing_fx_rate():
    values = pd.DataFrame({"USD": [100.0]})

    with pytest.raises(ValueError, match="missing for: USD"):
        convert_frame_to_base_currency(values, {})


def test_conversion_rejects_non_positive_fx_rate():
    values = pd.DataFrame({"USD": [100.0]})

    with pytest.raises(ValueError, match="must be positive"):
        convert_frame_to_base_currency(
            values,
            {"USD": 0.0},
        )
