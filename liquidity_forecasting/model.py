import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.linalg import LinAlgError
from scipy.stats import norm
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.statespace.sarimax import SARIMAX

from liquidity_forecasting.evaluation import seasonal_naive_forecast


@dataclass(frozen=True)
class ForecastResult:
    mean: pd.Series
    lower: pd.Series
    upper: pd.Series
    converged: bool
    model_name: str = "SARIMAX"


def seasonal_naive_fallback(
    series: pd.Series,
    periods: int,
    alpha: float = 0.05,
    season_length: int = 7,
    frequency: str = "D",
) -> ForecastResult:
    """Return a seasonal-naive forecast with empirical intervals."""
    mean = seasonal_naive_forecast(
        series,
        periods=periods,
        season_length=season_length,
        frequency=frequency,
    )

    values = np.asarray(series, dtype=float)
    seasonal_errors = values[season_length:] - values[:-season_length]

    if len(seasonal_errors) > 1:
        error_scale = float(np.std(seasonal_errors, ddof=1))
    else:
        error_scale = 0.0

    critical_value = float(norm.ppf(1 - alpha / 2))
    interval_width = critical_value * error_scale

    lower = pd.Series(
        mean.to_numpy() - interval_width,
        index=mean.index,
        name=series.name,
    )
    upper = pd.Series(
        mean.to_numpy() + interval_width,
        index=mean.index,
        name=series.name,
    )

    return ForecastResult(
        mean=mean,
        lower=lower,
        upper=upper,
        converged=False,
        model_name="Seasonal Naive (fallback)",
    )


def forecast_currency_with_intervals(
    df: pd.DataFrame,
    currency: str,
    periods: int = 30,
    order: tuple[int, int, int] = (1, 1, 1),
    seasonal: tuple[int, int, int, int] = (1, 1, 1, 7),
    alpha: float = 0.05,
    frequency: str = "D",
) -> ForecastResult:
    """Fit SARIMAX, falling back when fitting fails or does not converge."""
    if not 0 < alpha < 1:
        raise ValueError("Alpha must be between zero and one.")

    series = df[currency]

    try:
        with warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("always", ConvergenceWarning)

            model = SARIMAX(
                series,
                order=order,
                seasonal_order=seasonal,
            )
            fitted_model = model.fit(disp=False)

        convergence_warning = any(
            issubclass(warning.category, ConvergenceWarning)
            for warning in captured_warnings
        )

        converged = bool(
            fitted_model.mle_retvals.get(
                "converged",
                not convergence_warning,
            )
        )

        if not converged or convergence_warning:
            return seasonal_naive_fallback(
                series,
                periods=periods,
                alpha=alpha,
                season_length=seasonal[3],
                frequency=frequency,
            )

        prediction = fitted_model.get_forecast(steps=periods)
        confidence_intervals = prediction.conf_int(alpha=alpha)

        future_index = pd.date_range(
            start=series.index.max() + pd.tseries.frequencies.to_offset(frequency),
            periods=periods,
            freq=frequency,
        )

        mean = pd.Series(
            np.asarray(prediction.predicted_mean, dtype=float),
            index=future_index,
            name=currency,
        )
        lower = pd.Series(
            np.asarray(confidence_intervals.iloc[:, 0], dtype=float),
            index=future_index,
            name=currency,
        )
        upper = pd.Series(
            np.asarray(confidence_intervals.iloc[:, 1], dtype=float),
            index=future_index,
            name=currency,
        )

        return ForecastResult(
            mean=mean,
            lower=lower,
            upper=upper,
            converged=True,
            model_name="SARIMAX",
        )
    except (ArithmeticError, LinAlgError, RuntimeError, ValueError):
        return seasonal_naive_fallback(
            series,
            periods=periods,
            alpha=alpha,
            season_length=seasonal[3],
            frequency=frequency,
        )


def forecast_currency(
    df: pd.DataFrame,
    currency: str,
    periods: int = 30,
    order: tuple[int, int, int] = (1, 1, 1),
    seasonal: tuple[int, int, int, int] = (1, 1, 1, 7),
) -> pd.Series:
    """Return the mean from the production forecasting pipeline."""
    result = forecast_currency_with_intervals(
        df=df,
        currency=currency,
        periods=periods,
        order=order,
        seasonal=seasonal,
    )

    return result.mean
