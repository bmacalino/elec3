"""ARIMA and SARIMA, with and without the exchange rate and inflation (ARIMAX, SARIMAX)."""

import itertools
import warnings

import pandas as pd
from joblib import Parallel, delayed
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

from remittrend import config
from remittrend.models.base import (
    INDICATORS,
    INTERVAL_LEVEL,
    TARGET,
    Forecaster,
    hold_indicators,
    with_future,
)

MAX_P_Q = {False: 3, True: 2}  # non-seasonal orders tried: fewer when seasonal terms are added
MAX_SEASONAL_P_Q = 1


def _is_stationary(series: pd.Series) -> bool:
    p_value = adfuller(series.dropna(), autolag="AIC", result_object=False)[1]
    return p_value < 0.05


def _fit(endog, exog, order, seasonal_order, trend):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(endog, exog=exog, order=order, seasonal_order=seasonal_order, trend=trend)
        return model.fit(disp=False, maxiter=200)


def _aicc(endog, order, seasonal_order, trend) -> float | None:
    """AICc of one candidate, or None if it cannot be fitted or does not converge."""
    try:
        result = _fit(endog, None, order, seasonal_order, trend)
    except Exception:
        return None
    if not result.mle_retvals.get("converged", True) or not pd.notna(result.aicc):
        return None
    return float(result.aicc)


def select_order(endog: pd.Series, seasonal: bool) -> dict:
    """Choose the model orders on the given (training) series.

    Differencing comes from the ADF test: for ARIMA on the series itself, for
    SARIMA after one seasonal difference. The remaining orders, and whether to
    include a constant (drift), are chosen by the lowest AICc over a small grid.
    """
    period = config.SEASONAL_PERIOD
    if seasonal:
        seasonal_d = 1
        d = 0 if _is_stationary(endog.diff(period)) else 1
        seasonal_grid = range(MAX_SEASONAL_P_Q + 1)
    else:
        seasonal_d = 0
        d = 0 if _is_stationary(endog) else 1
        seasonal_grid = [0]

    orders = range(MAX_P_Q[seasonal] + 1)
    candidates = [
        ((p, d, q), (sp, seasonal_d, sq, period) if seasonal else (0, 0, 0, 0), trend)
        for p, q, sp, sq, trend in itertools.product(
            orders, orders, seasonal_grid, seasonal_grid, ("n", "c")
        )
    ]
    # The candidates are independent, so they are fitted on all processor cores.
    scores = Parallel(n_jobs=-1)(delayed(_aicc)(endog, *candidate) for candidate in candidates)
    fitted = [(score, candidate) for score, candidate in zip(scores, candidates) if score is not None]
    if not fitted:
        raise RuntimeError("No ARIMA model could be fitted")
    score, (order, seasonal_order, trend) = min(fitted, key=lambda item: item[0])
    return {"order": order, "seasonal_order": seasonal_order, "trend": trend, "aicc": score}


def describe_order(order, seasonal_order, trend) -> str:
    text = f"ARIMA({order[0]},{order[1]},{order[2]})"
    if seasonal_order[3]:
        text = f"S{text}({seasonal_order[0]},{seasonal_order[1]},{seasonal_order[2]})[{seasonal_order[3]}]"
    if trend == "c":
        text += " with drift" if order[1] + seasonal_order[1] else " with constant"
    return text


class ArimaForecaster(Forecaster):
    family = "statistical"
    has_intervals = True
    # The interval follows from the model's own estimate of its error variance.
    interval_method = "model"

    def __init__(self, key, name, order, seasonal_order, trend, uses_indicators=False):
        self.key = key
        self.name = name
        self.order = tuple(order)
        self.seasonal_order = tuple(seasonal_order)
        self.trend = trend
        self.uses_indicators = uses_indicators
        self.spec = describe_order(self.order, self.seasonal_order, trend)
        if uses_indicators:
            self.spec += f", indicators lagged {config.INDICATOR_LAG} months"

    def _exog(self, frame: pd.DataFrame) -> pd.DataFrame:
        lag = config.INDICATOR_LAG
        return frame[list(INDICATORS)].shift(lag).add_suffix(f"_lag{lag}")

    def fit(self, history):
        self.history = history
        endog = history[TARGET]
        exog = None
        if self.uses_indicators:
            # The first months have no lagged indicator values and are left out.
            exog = self._exog(history).dropna()
            endog = endog.loc[exog.index]
        self.training_rows = len(endog)
        self.result = _fit(endog, exog, self.order, self.seasonal_order, self.trend)
        return self

    def forecast(self, horizon, future_indicators=None):
        exog = None
        if self.uses_indicators:
            if future_indicators is None:
                future_indicators = hold_indicators(self.history, horizon)
            combined = with_future(self.history, future_indicators.iloc[:horizon])
            exog = self._exog(combined).iloc[-horizon:]
        frame = self.result.get_forecast(steps=horizon, exog=exog).summary_frame(
            alpha=1 - INTERVAL_LEVEL
        )
        return pd.DataFrame(
            {
                "mean": frame["mean"].to_numpy(),
                "lower": frame["mean_ci_lower"].to_numpy(),
                "upper": frame["mean_ci_upper"].to_numpy(),
            },
            index=pd.period_range(self.history.index[-1] + 1, periods=horizon, freq="M"),
        )

    def details(self):
        if not self.uses_indicators:
            return {}
        names = [f"{column}_lag{config.INDICATOR_LAG}" for column in INDICATORS]
        used = self._exog(self.history).dropna()
        return {
            "trained_range": {
                column: [float(used[name].min()), float(used[name].max())]
                for column, name in zip(INDICATORS, names)
            },
            "coefficients": [
                {
                    "term": name,
                    "coefficient": float(self.result.params[name]),
                    "p_value": float(self.result.pvalues[name]),
                }
                for name in names
            ]
        }
