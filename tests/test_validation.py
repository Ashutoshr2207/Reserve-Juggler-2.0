import pandas as pd
import pytest

from liquidity_forecasting.validation import validate_cashflow_data


def make_valid_data() -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=60, freq="D")
    return pd.DataFrame(
        {
            "EUR": range(60),
            "USD": range(100, 160),
        },
        index=dates,
    )


def test_valid_cashflow_data_passes():
    validate_cashflow_data(make_valid_data())


def test_rejects_non_datetime_index():
    data = make_valid_data().reset_index(drop=True)

    with pytest.raises(ValueError, match="DatetimeIndex"):
        validate_cashflow_data(data)


def test_rejects_duplicate_dates():
    data = make_valid_data()
    data.index = list(data.index[:-1]) + [data.index[-2]]

    with pytest.raises(ValueError, match="duplicate dates"):
        validate_cashflow_data(data)


def test_rejects_insufficient_history():
    data = make_valid_data().iloc[:30]

    with pytest.raises(ValueError, match="at least 60 observations"):
        validate_cashflow_data(data)


def test_rejects_non_numeric_columns():
    data = make_valid_data()
    data["Comment"] = "example"

    with pytest.raises(ValueError, match="must be numeric"):
        validate_cashflow_data(data)


def test_rejects_missing_values():
    data = make_valid_data()
    data.iloc[10, 0] = None

    with pytest.raises(ValueError, match="missing values"):
        validate_cashflow_data(data)
