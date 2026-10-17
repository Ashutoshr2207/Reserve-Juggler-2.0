import pandas as pd


def validate_cashflow_data(
    data: pd.DataFrame,
    min_observations: int = 60,
) -> None:
    """Validate cashflow data before forecasting."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Cashflow data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Cashflow data cannot be empty.")

    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Cashflow data must use a DatetimeIndex.")

    if data.index.has_duplicates:
        raise ValueError("Cashflow data contains duplicate dates.")

    if not data.index.is_monotonic_increasing:
        raise ValueError("Cashflow dates must be sorted in ascending order.")

    if len(data) < min_observations:
        raise ValueError(
            f"Cashflow data must contain at least {min_observations} observations."
        )

    if len(data.columns) == 0:
        raise ValueError("Cashflow data must contain at least one currency.")

    non_numeric_columns = data.select_dtypes(exclude="number").columns.tolist()
    if non_numeric_columns:
        columns = ", ".join(map(str, non_numeric_columns))
        raise ValueError(
            f"Cashflow columns must be numeric. Invalid columns: {columns}."
        )

    missing_columns = data.columns[data.isna().all()].tolist()
    if missing_columns:
        columns = ", ".join(map(str, missing_columns))
        raise ValueError(f"Cashflow columns cannot be entirely empty: {columns}.")

    if data.isna().any().any():
        raise ValueError(
            "Cashflow data still contains missing values after preprocessing."
        )
