"""Comparing forecasts with what actually happened."""

import numpy as np
import pandas as pd
from scipy import stats

from remittrend import config
from remittrend.models.base import INDICATOR_COLUMNS, TARGET, Forecaster, hold_indicators


def split(monthly: pd.DataFrame) -> tuple[pd.PeriodIndex, pd.PeriodIndex]:
    """Chronological split: the last config.TEST_MONTHS months are the testing period."""
    return monthly.index[: -config.TEST_MONTHS], monthly.index[-config.TEST_MONTHS :]


def error_metrics(actual, predicted) -> dict:
    """MAE and RMSE in the unit of the series (US$ million); MAPE in percent."""
    actual = np.asarray(actual, dtype=float)
    error = np.asarray(predicted, dtype=float) - actual
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mape": float(np.mean(np.abs(error / actual)) * 100),
    }


def forecast_at(
    fitted: Forecaster,
    monthly: pd.DataFrame,
    origin: pd.Period,
    horizon: int = config.FORECAST_HORIZON,
    indicators: str = "held",
) -> dict:
    """Score a model already fitted on the months up to the origin.

    indicators="held": the exchange rate and inflation stay at their last
    observed values, as they would for a forecast made at the origin.
    indicators="actual": the model is given the values that later occurred,
    which no real forecast could have; reported only as a comparison.
    """
    history = monthly.loc[:origin]
    actual = monthly.loc[origin + 1 : origin + horizon]
    if indicators == "actual":
        future = actual[list(INDICATOR_COLUMNS)]
    else:
        future = hold_indicators(history, horizon)

    predicted = fitted.forecast(horizon, future)
    values = actual[TARGET].to_numpy(dtype=float)
    result = {
        "origin": str(origin),
        "months": [str(month) for month in actual.index],
        "predicted": predicted["mean"].tolist(),
        "lower": predicted["lower"].tolist(),
        "upper": predicted["upper"].tolist(),
        "errors": (predicted["mean"].to_numpy(dtype=float) - values).tolist(),
        **error_metrics(values, predicted["mean"]),
    }
    if predicted["lower"].notna().all():
        inside = (values >= predicted["lower"].to_numpy()) & (values <= predicted["upper"].to_numpy())
        result["coverage"] = {"inside": int(inside.sum()), "months": int(len(values))}
    return result


def evaluate_at(
    model: Forecaster,
    monthly: pd.DataFrame,
    origin: pd.Period,
    horizon: int = config.FORECAST_HORIZON,
    indicators: str = "held",
) -> dict:
    """Fit on the months up to the origin, forecast the next `horizon` months, score them."""
    return forecast_at(model.fit(monthly.loc[:origin]), monthly, origin, horizon, indicators)


def rolling_origins(
    monthly: pd.DataFrame,
    horizon: int = config.FORECAST_HORIZON,
    windows: int = config.ROLLING_WINDOWS,
    step: int = config.ROLLING_STEP,
) -> list[pd.Period]:
    """Forecast origins of the test windows; the last one is the main test split."""
    last = monthly.index[-1] - horizon
    return [last - step * k for k in range(windows - 1, -1, -1)]


def diebold_mariano(errors_a, errors_b, lags: int) -> dict:
    """Do two models' squared forecast errors differ by more than chance?

    Diebold-Mariano test on paired errors. The variance uses Newey-West weights
    over `lags` lags, because errors from the same multi-month forecast are
    correlated; the p-value uses the t distribution (Harvey, Leybourne and
    Newbold's small-sample form). A p-value of 0.05 or more means the two
    models cannot be told apart on these forecasts.
    """
    difference = np.asarray(errors_a, dtype=float) ** 2 - np.asarray(errors_b, dtype=float) ** 2
    n = len(difference)
    centred = difference - difference.mean()
    variance = float(centred @ centred) / n
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1 - lag / (lags + 1)
        variance += 2 * weight * float(centred[lag:] @ centred[:-lag]) / n
    if variance <= 0:
        return {"statistic": None, "p_value": None}
    statistic = difference.mean() / np.sqrt(variance / n)
    p_value = 2 * stats.t.sf(abs(statistic), df=n - 1)
    return {"statistic": float(statistic), "p_value": float(p_value)}
