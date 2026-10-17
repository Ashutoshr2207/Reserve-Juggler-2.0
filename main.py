from liquidity_forecasting.allocation import (
    DEFAULT_PRIORITY_WEIGHTS,
    DEFAULT_TRANSFER_COST_RATES,
    optimize_funding_allocation,
)
from liquidity_forecasting.balances import (
    DEFAULT_MINIMUM_BUFFERS,
    DEFAULT_OPENING_BALANCES,
    calculate_liquidity_shortfalls,
    project_balances,
)
from liquidity_forecasting.data import (
    generate_sample_cashflows,
    preprocess_data,
)
from liquidity_forecasting.export import save_to_excel
from liquidity_forecasting.fx import (
    BASE_CURRENCY,
    DEFAULT_FX_TO_EUR,
    convert_frame_to_base_currency,
)
from liquidity_forecasting.model import (
    forecast_currency_with_intervals,
)
from liquidity_forecasting.plotting import plot_forecasts
from liquidity_forecasting.validation import validate_cashflow_data


def main():
    cashflows = generate_sample_cashflows()
    cashflows = preprocess_data(cashflows)
    validate_cashflow_data(cashflows)

    forecast_results = {
        currency: forecast_currency_with_intervals(
            cashflows,
            currency,
        )
        for currency in cashflows.columns
    }

    forecasts = {currency: result.mean for currency, result in forecast_results.items()}

    fallback_currencies = [
        currency
        for currency, result in forecast_results.items()
        if result.model_name != "SARIMAX"
    ]

    if fallback_currencies:
        print("Seasonal-naive fallback used for: " + ", ".join(fallback_currencies))

    opening_balances = {
        currency: DEFAULT_OPENING_BALANCES[currency] for currency in forecasts
    }

    minimum_buffers = {
        currency: DEFAULT_MINIMUM_BUFFERS[currency] for currency in forecasts
    }

    fx_rates = {currency: DEFAULT_FX_TO_EUR[currency] for currency in forecasts}

    transfer_cost_rates = {
        currency: DEFAULT_TRANSFER_COST_RATES[currency] for currency in forecasts
    }

    priority_weights = {
        currency: DEFAULT_PRIORITY_WEIGHTS[currency] for currency in forecasts
    }

    projected_balances = project_balances(
        opening_balances,
        forecasts,
    )

    shortfalls = calculate_liquidity_shortfalls(
        projected_balances,
        minimum_buffers,
    )

    shortfalls_in_base_currency = convert_frame_to_base_currency(
        shortfalls,
        fx_rates,
    )

    maximum_shortfalls_in_base = shortfalls_in_base_currency.max()

    available_funds = 100_000.0

    funding_recommendations = optimize_funding_allocation(
        maximum_shortfalls_in_base.to_dict(),
        available_funds,
        transfer_cost_rates,
        priority_weights,
    )

    print("Projected minimum balances:")
    for currency, balance in projected_balances.min().items():
        print(f"{currency}: {balance:,.2f}")

    print(f"\nMaximum liquidity shortfalls in {BASE_CURRENCY}:")
    for currency, shortfall in maximum_shortfalls_in_base.items():
        print(f"{currency}: {shortfall:,.2f}")

    print(
        f"\nRecommended funding in {BASE_CURRENCY} (available: {available_funds:,.2f}):"
    )
    for currency, amount in funding_recommendations.items():
        print(f"{currency}: {amount:,.2f}")

    estimated_transfer_cost = sum(
        funding_recommendations[currency] * transfer_cost_rates[currency]
        for currency in funding_recommendations
    )

    print(
        f"\nEstimated transfer cost in {BASE_CURRENCY}: {estimated_transfer_cost:,.2f}"
    )

    save_to_excel(
        cashflows,
        forecasts,
        funding_recommendations,
        projected_balances=projected_balances,
        liquidity_shortfalls=shortfalls,
        forecast_results=forecast_results,
    )

    plot_forecasts(cashflows, forecasts)


if __name__ == "__main__":
    main()
