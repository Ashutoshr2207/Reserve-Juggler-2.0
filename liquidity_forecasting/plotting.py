import matplotlib.pyplot as plt
import pandas as pd


def plot_forecasts(
    historical_data: pd.DataFrame,
    forecasts: dict[str, pd.Series],
    show: bool = True,
):
    """Plot historical and forecast values for each currency."""
    if historical_data.empty:
        raise ValueError("Historical data cannot be empty.")

    if not forecasts:
        raise ValueError("At least one forecast is required.")

    figure, axes = plt.subplots(
        nrows=len(forecasts),
        ncols=1,
        figsize=(12, 4 * len(forecasts)),
        squeeze=False,
    )

    for axis, (currency, forecast) in zip(
        axes.flatten(),
        forecasts.items(),
    ):
        if currency not in historical_data.columns:
            raise ValueError(f"Currency '{currency}' is missing from historical data.")

        historical_series = historical_data[currency].tail(90)
        forecast_series = pd.Series(forecast).copy()

        axis.plot(
            historical_series.index,
            historical_series.values,
            label="Historical",
        )
        axis.plot(
            forecast_series.index,
            forecast_series.values,
            label="Forecast",
            linestyle="--",
        )

        axis.set_title(f"{currency} liquidity forecast")
        axis.set_xlabel("Date")
        axis.set_ylabel("Daily net cashflow (local currency)")
        axis.legend()
        axis.grid(alpha=0.3)

    figure.tight_layout()

    if show:
        plt.show()

    return figure
