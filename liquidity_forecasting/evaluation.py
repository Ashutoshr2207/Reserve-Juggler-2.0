from typing import Callable

import numpy as np
import pandas as pd


def seasonal_naive_forecast(
    series: pd.Series,
    periods: int,
    season_length: int = 7,
    frequency: str = "D",
) -> pd.Series:
    """Forecast by repeating the most recent seasonal cycle."""
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("Series must use a DatetimeIndex.")

    if periods <= 0:
        raise ValueError("Forecast periods must be positive.")

    if season_length <= 0:
        raise ValueError("Season length must be positive.")

    if len(series) < season_length:
        raise ValueError("Series must contain at least one complete seasonal cycle.")

    recent_cycle = series.iloc[-season_length:].to_numpy()
    forecast_values = np.resize(recent_cycle, periods)

    future_index = pd.date_range(
        start=series.index.max() + pd.tseries.frequencies.to_offset(frequency),
        periods=periods,
        freq=frequency,
    )

    return pd.Series(
        forecast_values,
        index=future_index,
        name=series.name,
    )


def mean_absolute_error(
    actual: pd.Series,
    predicted: pd.Series,
) -> float:
    """Calculate mean absolute forecast error."""
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted values must have equal lengths.")

    if len(actual) == 0:
        raise ValueError("Forecast evaluation data cannot be empty.")

    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)

    return float(np.mean(np.abs(actual_values - predicted_values)))


def mean_absolute_scaled_error(
    actual: pd.Series,
    predicted: pd.Series,
    training_series: pd.Series,
    season_length: int = 7,
) -> float:
    """Calculate error relative to an in-sample seasonal-naive model."""
    if len(training_series) <= season_length:
        raise ValueError("Training data must exceed the season length.")

    forecast_error = mean_absolute_error(actual, predicted)

    training_values = np.asarray(
        training_series,
        dtype=float,
    )

    naive_errors = np.abs(
        training_values[season_length:] - training_values[:-season_length]
    )
    scale = float(np.mean(naive_errors))

    if scale == 0:
        raise ValueError("MASE cannot be calculated when the scale is zero.")

    return forecast_error / scale


def rolling_backtest_currency(
    data: pd.DataFrame,
    currency: str,
    forecast_function: Callable[..., pd.Series],
    horizon: int = 7,
    folds: int = 3,
    season_length: int = 7,
) -> pd.DataFrame:
    """Compare a forecasting function with a seasonal-naive baseline."""
    if currency not in data.columns:
        raise ValueError(f"Currency '{currency}' is missing.")

    if horizon <= 0:
        raise ValueError("Backtest horizon must be positive.")

    if folds <= 0:
        raise ValueError("Backtest folds must be positive.")

    required_observations = folds * horizon + season_length + 1

    if len(data) < required_observations:
        raise ValueError(
            f"Backtesting requires at least {required_observations} observations."
        )

    results = []

    for fold in range(folds):
        test_start = len(data) - (folds - fold) * horizon
        test_end = test_start + horizon

        training_data = data.iloc[:test_start]
        actual = data[currency].iloc[test_start:test_end]

        model_forecast = forecast_function(
            training_data,
            currency,
            periods=horizon,
        )

        naive_forecast = seasonal_naive_forecast(
            training_data[currency],
            periods=horizon,
            season_length=season_length,
        )

        predictions = {
            "Forecast Pipeline": model_forecast,
            "Seasonal Naive": naive_forecast,
        }

        for model_name, predicted in predictions.items():
            results.append(
                {
                    "Fold": fold + 1,
                    "Model": model_name,
                    "Test Start": actual.index.min(),
                    "Test End": actual.index.max(),
                    "MAE": mean_absolute_error(
                        actual,
                        predicted,
                    ),
                    "MASE": mean_absolute_scaled_error(
                        actual,
                        predicted,
                        training_data[currency],
                        season_length=season_length,
                    ),
                }
            )

    return pd.DataFrame(results)


def summarize_backtest_results(
    results: pd.DataFrame,
) -> pd.DataFrame:
    """Average forecast metrics across backtest folds."""
    required_columns = {"Model", "MAE", "MASE"}

    missing_columns = required_columns - set(results.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Backtest results are missing columns: {missing}.")

    if results.empty:
        raise ValueError("Backtest results cannot be empty.")

    summary = (
        results.groupby("Model")[["MAE", "MASE"]]
        .mean()
        .reset_index()
        .sort_values("MASE")
        .reset_index(drop=True)
    )

    return summary
