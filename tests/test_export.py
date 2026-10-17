from io import BytesIO
from zipfile import ZipFile

import pandas as pd

from liquidity_forecasting.export import save_to_excel
from liquidity_forecasting.model import ForecastResult


def test_excel_export_contains_expected_sheets():
    historical_index = pd.date_range(
        "2025-01-01",
        periods=3,
        freq="D",
    )
    forecast_index = pd.date_range(
        "2025-01-04",
        periods=2,
        freq="D",
    )

    cashflows = pd.DataFrame(
        {"EUR": [100.0, -50.0, 25.0]},
        index=historical_index,
    )
    forecasts = {
        "EUR": pd.Series(
            [20.0, -10.0],
            index=forecast_index,
            name="EUR",
        )
    }
    forecast_results = {
        "EUR": ForecastResult(
            mean=forecasts["EUR"],
            lower=pd.Series(
                [10.0, -20.0],
                index=forecast_index,
                name="EUR",
            ),
            upper=pd.Series(
                [30.0, 0.0],
                index=forecast_index,
                name="EUR",
            ),
            converged=True,
        )
    }
    projected_balances = pd.DataFrame(
        {"EUR": [1_020.0, 1_010.0]},
        index=forecast_index,
    )
    liquidity_shortfalls = pd.DataFrame(
        {"EUR": [0.0, 10.0]},
        index=forecast_index,
    )
    funding_recommendations = {"EUR": 1_000.0}

    output = BytesIO()

    save_to_excel(
        cashflows,
        forecasts,
        funding_recommendations,
        filename=output,
        projected_balances=projected_balances,
        liquidity_shortfalls=liquidity_shortfalls,
        forecast_results=forecast_results,
    )

    output.seek(0)

    with ZipFile(output) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")

    assert "Historical_Cashflows" in workbook_xml
    assert "Forecasts" in workbook_xml
    assert "Forecast_Lower_95" in workbook_xml
    assert "Forecast_Upper_95" in workbook_xml
    assert "Projected_Balances" in workbook_xml
    assert "Liquidity_Shortfalls" in workbook_xml
    assert "Funding_Recommendations" in workbook_xml
