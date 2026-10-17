import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from liquidity_forecasting.plotting import plot_forecasts


def test_plot_forecasts_creates_historical_and_forecast_lines():
    historical_index = pd.date_range("2025-01-01", periods=10, freq="D")
    forecast_index = pd.date_range("2025-01-11", periods=3, freq="D")

    historical_data = pd.DataFrame(
        {"EUR": range(10)},
        index=historical_index,
    )
    forecasts = {
        "EUR": pd.Series([10, 11, 12], index=forecast_index),
    }

    figure = plot_forecasts(
        historical_data,
        forecasts,
        show=False,
    )

    assert len(figure.axes) == 1
    assert len(figure.axes[0].lines) == 2
    assert figure.axes[0].get_title() == "EUR liquidity forecast"

    plt.close(figure)
