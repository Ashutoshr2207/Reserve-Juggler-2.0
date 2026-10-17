import pandas as pd

from liquidity_forecasting.data import (
    generate_sample_cashflows,
    preprocess_data,
)


def test_generate_sample_cashflows_default_shape():
    """Sample data should contain the expected currencies."""
    data = generate_sample_cashflows()

    assert isinstance(data.index, pd.DatetimeIndex)
    assert not data.empty
    assert set(data.columns) == {
        "EUR",
        "USD",
        "JPY",
        "BRL",
        "INR",
        "AUD",
    }


def test_preprocess_data_forward_fills_missing_values():
    """Preprocessing should forward-fill missing values."""
    data = generate_sample_cashflows().copy()
    data.iloc[10, 0] = None

    assert pd.isna(data.iloc[10, 0])

    processed = preprocess_data(data)

    assert not processed.isna().any().any()
    assert processed.iloc[10, 0] == processed.iloc[9, 0]


def test_sample_cashflows_are_reproducible():
    first = generate_sample_cashflows(seed=123)
    second = generate_sample_cashflows(seed=123)

    pd.testing.assert_frame_equal(first, second)


def test_sample_cashflows_change_with_seed():
    first = generate_sample_cashflows(seed=123)
    second = generate_sample_cashflows(seed=456)

    assert not first.equals(second)


def test_sample_cashflows_include_inflows_and_outflows():
    data = generate_sample_cashflows()

    assert (data > 0).any().all()
    assert (data < 0).any().all()
