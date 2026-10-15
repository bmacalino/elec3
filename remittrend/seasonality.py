"""Seasonal analysis of a monthly series: STL decomposition and the calendar-month pattern."""

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from remittrend import config

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def decompose(series: pd.Series) -> pd.DataFrame:
    """STL decomposition into trend, seasonal and residual parts.

    The robust option keeps unusual months, such as the 2020 drop, from
    distorting the seasonal pattern.
    """
    values = pd.Series(series.to_numpy(dtype=float), index=series.index.to_timestamp())
    result = STL(values, period=config.SEASONAL_PERIOD, robust=True).fit()
    return pd.DataFrame(
        {
            "observed": series.to_numpy(dtype=float),
            "trend": result.trend.to_numpy(),
            "seasonal": result.seasonal.to_numpy(),
            "residual": result.resid.to_numpy(),
        },
        index=series.index,
    )


def seasonal_strength(components: pd.DataFrame) -> float:
    """0 = no seasonality, 1 = strongly seasonal (Hyndman & Athanasopoulos, 2021)."""
    residual = components["residual"]
    return float(max(0.0, 1 - residual.var() / (components["seasonal"] + residual).var()))


def centred_moving_average(series: pd.Series) -> pd.Series:
    """Centred 12-month moving average (2x12): the level of the series without the season."""
    trailing = series.rolling(12).mean()
    return (trailing.shift(-5) + trailing.shift(-6)) / 2


def ratio_to_trend(series: pd.Series) -> pd.Series:
    """Each month as a percentage of the centred moving average around it.

    100 means an ordinary month; 110 means 10% above the level of that time.
    Undefined for the first and last six months of the series.
    """
    return series / centred_moving_average(series) * 100


def monthly_profile(series: pd.Series) -> pd.DataFrame:
    """One row per calendar month: average level, seasonal index and rank.

    The average uses complete calendar years only. The seasonal index is the
    mean of ratio_to_trend for that calendar month, rescaled so the twelve
    indices average 100; it is not affected by the upward trend or by a
    half-finished final year.
    """
    years = series.groupby(series.index.year).count()
    complete = series[series.index.year.isin(years[years == 12].index)]
    average = complete.groupby(complete.index.month).mean()

    ratio = ratio_to_trend(series).dropna()
    index = ratio.groupby(ratio.index.month).mean()
    index = index / index.mean() * 100

    profile = pd.DataFrame(
        {
            "month": range(1, 13),
            "label": MONTH_LABELS,
            "average": average.reindex(range(1, 13)).to_numpy(),
            "seasonal_index": index.reindex(range(1, 13)).to_numpy(),
        }
    )
    profile["rank"] = profile["seasonal_index"].rank(ascending=False).astype(int)
    return profile


def month_by_year(series: pd.Series) -> pd.DataFrame:
    """Years as rows, calendar months 1-12 as columns; missing months are NaN."""
    table = pd.DataFrame(
        {"year": series.index.year, "month": series.index.month, "value": series.to_numpy(dtype=float)}
    ).pivot(index="year", columns="month", values="value")
    return table.reindex(columns=range(1, 13))


def analyse(series: pd.Series) -> dict:
    """Everything the seasonality page shows, as plain lists and numbers."""
    components = decompose(series)
    profile = monthly_profile(series)
    ranked = profile.sort_values("seasonal_index", ascending=False)
    levels = month_by_year(series)
    ratios = month_by_year(ratio_to_trend(series))
    return {
        "strength": seasonal_strength(components),
        "profile": profile.to_dict(orient="records"),
        "highest_months": ranked["label"].head(3).tolist(),
        "lowest_months": ranked["label"].tail(3).tolist()[::-1],
        "average_years": [int(y) for y, n in series.groupby(series.index.year).count().items() if n == 12],
        "decomposition": {
            "months": [str(m) for m in components.index],
            **{column: components[column].tolist() for column in components.columns},
        },
        "by_year": {
            "years": [int(year) for year in levels.index],
            "months": MONTH_LABELS,
            "values": _rows(levels),
            "percent_of_trend": _rows(ratios.reindex(levels.index)),
        },
    }


def _rows(table: pd.DataFrame) -> list[list[float | None]]:
    return [[None if np.isnan(v) else float(v) for v in row] for row in table.to_numpy(dtype=float)]
