import pandas as pd
import pytest

from liquidity_forecasting.evaluation import (
    mean_absolute_error,
    mean_absolute_scaled_error,
    rolling_backtest_currency,
    seasonal_naive_forecast,
    summarize_backtest_results,
)


def test_seasonal_naive_repeats_latest_week():
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    series = pd.Series(range(10), index=dates, name="EUR")

    result = seasonal_naive_forecast(
        series,
        periods=10,
        season_length=7,
    )

    assert result.tolist() == [3, 4, 5, 6, 7, 8, 9, 3, 4, 5]
    assert result.index[0] == pd.Timestamp("2025-01-11")
    assert result.name == "EUR"


def test_seasonal_naive_rejects_insufficient_history():
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    series = pd.Series([1.0, 2.0, 3.0], index=dates)

    with pytest.raises(ValueError, match="complete seasonal cycle"):
        seasonal_naive_forecast(
            series,
            periods=2,
            season_length=7,
        )


def test_mean_absolute_error():
    actual = pd.Series([10.0, 20.0, 30.0])
    predicted = pd.Series([8.0, 24.0, 30.0])

    result = mean_absolute_error(actual, predicted)

    assert result == pytest.approx(2.0)


def test_mean_absolute_scaled_error():
    training = pd.Series([1.0, 2.0, 3.0, 4.0])
    actual = pd.Series([5.0, 6.0])
    predicted = pd.Series([4.0, 5.0])

    result = mean_absolute_scaled_error(
        actual,
        predicted,
        training,
        season_length=1,
    )

    assert result == pytest.approx(1.0)


def test_mean_absolute_error_rejects_different_lengths():
    with pytest.raises(ValueError, match="equal lengths"):
        mean_absolute_error(
            pd.Series([1.0]),
            pd.Series([1.0, 2.0]),
        )


def test_rolling_backtest_returns_both_models_for_each_fold():
    dates = pd.date_range("2025-01-01", periods=40, freq="D")
    data = pd.DataFrame(
        {"EUR": [float(value) for value in range(40)]},
        index=dates,
    )

    training_lengths = []

    def simple_forecast(training_data, currency, periods):
        training_lengths.append(len(training_data))

        future_dates = pd.date_range(
            training_data.index.max() + pd.Timedelta(days=1),
            periods=periods,
            freq="D",
        )

        return pd.Series(
            [training_data[currency].iloc[-1]] * periods,
            index=future_dates,
            name=currency,
        )

    result = rolling_backtest_currency(
        data,
        "EUR",
        simple_forecast,
        horizon=3,
        folds=2,
        season_length=7,
    )

    assert len(result) == 4
    assert set(result["Model"]) == {
        "Forecast Pipeline",
        "Seasonal Naive",
    }
    assert set(result["Fold"]) == {1, 2}
    assert (result["MAE"] >= 0).all()
    assert (result["MASE"] >= 0).all()
    assert training_lengths == [34, 37]


def test_rolling_backtest_rejects_insufficient_history():
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    data = pd.DataFrame(
        {"EUR": range(10)},
        index=dates,
    )

    with pytest.raises(ValueError, match="requires at least"):
        rolling_backtest_currency(
            data,
            "EUR",
            lambda data, currency, periods: pd.Series(),
            horizon=3,
            folds=2,
            season_length=7,
        )


def test_summarize_backtest_results():
    results = pd.DataFrame(
        {
            "Model": [
                "SARIMAX",
                "Seasonal Naive",
                "SARIMAX",
                "Seasonal Naive",
            ],
            "MAE": [8.0, 10.0, 6.0, 12.0],
            "MASE": [0.8, 1.0, 0.6, 1.2],
        }
    )

    summary = summarize_backtest_results(results)

    assert summary["Model"].tolist() == [
        "SARIMAX",
        "Seasonal Naive",
    ]
    assert summary.loc[0, "MAE"] == pytest.approx(7.0)
    assert summary.loc[0, "MASE"] == pytest.approx(0.7)
