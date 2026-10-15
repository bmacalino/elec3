"""Trend measures for a monthly series: percentage changes, moving averages, direction."""

import pandas as pd

from remittrend import config

MOVING_AVERAGE_WINDOWS = (3, 6, 12)


def percent_changes(series: pd.Series) -> pd.DataFrame:
    """Change from the previous month and from the same month a year earlier, in percent."""
    return pd.DataFrame(
        {
            "mom_pct": series.pct_change(1) * 100,
            "yoy_pct": series.pct_change(12) * 100,
        }
    )


def moving_averages(series: pd.Series, windows=MOVING_AVERAGE_WINDOWS) -> pd.DataFrame:
    """Trailing moving averages: each value is the mean of that month and the ones before it."""
    return pd.DataFrame({f"ma_{window}": series.rolling(window).mean() for window in windows})


def year_to_date(series: pd.Series) -> pd.Series:
    """Running total within each calendar year."""
    return series.groupby(series.index.year).cumsum()


def classify_trend(series: pd.Series, start, end, band_pct: float | None = None) -> dict:
    """Whether the series is rising, falling or stable between two months.

    Judged on the 12-month moving average, so the yearly seasonal cycle is not
    mistaken for a trend. The change is expressed per year; within plus or minus
    band_pct per year the series is called stable.
    """
    band_pct = config.TREND_STABLE_BAND_PCT if band_pct is None else band_pct
    smooth = series.rolling(12).mean().loc[start:end].dropna()
    if len(smooth) < 2:
        return {"direction": None, "annual_change_pct": None, "from": None, "to": None}

    months = len(smooth) - 1
    annual = ((smooth.iloc[-1] / smooth.iloc[0]) ** (12 / months) - 1) * 100
    if annual > band_pct:
        direction = "rising"
    elif annual < -band_pct:
        direction = "falling"
    else:
        direction = "stable"
    return {
        "direction": direction,
        "annual_change_pct": float(annual),
        "from": str(smooth.index[0]),
        "to": str(smooth.index[-1]),
    }


def period_summary(series: pd.Series, start, end) -> dict:
    """Totals and the first-to-last change for the selected months."""
    part = series.loc[start:end]
    first, last = part.iloc[0], part.iloc[-1]
    return {
        "months": int(len(part)),
        "total": float(part.sum()),
        "average": float(part.mean()),
        "first": float(first),
        "last": float(last),
        "change_pct": float((last / first - 1) * 100),
        "highest_month": str(part.idxmax()),
        "lowest_month": str(part.idxmin()),
    }
