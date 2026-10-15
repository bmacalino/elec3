"""Random Forest and XGBoost on lagged features.

Decision trees cannot predict beyond the range of values they were trained on,
and remittances grow every year. The trees therefore predict the year-on-year
change, which has no trend, and the forecast in US dollars is rebuilt from the
value of the same month a year earlier.
"""

import math

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from xgboost import XGBRegressor

from remittrend import config
from remittrend.models.base import (
    INDICATORS,
    INTERVAL_LEVEL,
    TARGET,
    TARGET_YOY,
    Forecaster,
    hold_indicators,
    with_future,
)

REMITTANCE_LAGS = (1, 2, 3, 6)
MOVING_AVERAGES = (3, 6)
INDICATOR_LAGS = (config.INDICATOR_LAG, 6)
CV_SPLITS = 4
# Prediction intervals: forecast months are grouped in bands of this many
# months, and a backtest needs at least this much history to train on.
INTERVAL_BAND_MONTHS = 3
MIN_BACKTEST_HISTORY = 36

ESTIMATORS = {
    "random_forest": lambda params: RandomForestRegressor(
        random_state=config.RANDOM_SEED, n_jobs=1, **params
    ),
    "xgboost": lambda params: XGBRegressor(
        random_state=config.RANDOM_SEED, n_jobs=1, objective="reg:squarederror", **params
    ),
}

PARAM_GRIDS = {
    "random_forest": {
        "n_estimators": [300],
        "max_depth": [2, 3, 5, None],
        "min_samples_leaf": [1, 3, 5],
        "max_features": [0.5, 1.0],
    },
    "xgboost": {
        "n_estimators": [100, 300],
        "learning_rate": [0.03, 0.1],
        "max_depth": [2, 3],
        "min_child_weight": [1, 3],
        "subsample": [0.8],
    },
}


def make_features(frame: pd.DataFrame, uses_indicators: bool) -> pd.DataFrame:
    """Features for every month of the frame, built only from earlier months.

    Used for both training and forecasting, so the two cannot drift apart.
    """
    change = frame[TARGET_YOY]
    features = pd.DataFrame(index=frame.index)
    for lag in REMITTANCE_LAGS:
        features[f"remittance_yoy_lag{lag}"] = change.shift(lag)
    for window in MOVING_AVERAGES:
        features[f"remittance_yoy_mean{window}"] = change.shift(1).rolling(window).mean()
    features["month"] = frame.index.month
    if uses_indicators:
        for column in INDICATORS:
            for lag in INDICATOR_LAGS:
                features[f"{column}_lag{lag}"] = frame[column].shift(lag)
    return features


def training_set(history: pd.DataFrame, uses_indicators: bool) -> tuple[pd.DataFrame, pd.Series]:
    features = make_features(history, uses_indicators).dropna()
    return features, history.loc[features.index, TARGET_YOY]


def tune(history: pd.DataFrame, kind: str, uses_indicators: bool) -> dict:
    """Hyperparameters by time-series cross-validation within the given (training) months."""
    features, target = training_set(history, uses_indicators)
    search = GridSearchCV(
        ESTIMATORS[kind]({}),
        PARAM_GRIDS[kind],
        cv=TimeSeriesSplit(n_splits=CV_SPLITS),
        scoring="neg_root_mean_squared_error",
        n_jobs=-1,
    )
    search.fit(features, target)
    return search.best_params_


class TreeForecaster(Forecaster):
    family = "machine learning"
    # Trees give no interval of their own; it is taken from past forecast errors.
    interval_method = "backtest"

    def __init__(self, key, name, kind, params, uses_indicators=False):
        self.key = key
        self.name = name
        self.kind = kind
        self.params = dict(params)
        self.uses_indicators = uses_indicators
        self.spec = ", ".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        self.interval_half_width: list[float] | None = None

    @property
    def has_intervals(self) -> bool:
        return self.interval_half_width is not None

    def unfitted(self) -> "TreeForecaster":
        """A new model with the same settings and nothing learned."""
        return TreeForecaster(self.key, self.name, self.kind, self.params, self.uses_indicators)

    def fit(self, history):
        self.history = history
        features, target = training_set(history, self.uses_indicators)
        self.training_rows = len(features)
        self.feature_names = list(features.columns)
        self.feature_range = features.agg(["min", "max"])
        self.estimator = ESTIMATORS[self.kind](self.params).fit(features, target)
        # An interval belongs to the history it was measured on.
        self.interval_half_width = None
        return self

    def calibrate(self, horizon: int = config.FORECAST_HORIZON) -> "TreeForecaster":
        """Measure prediction intervals on the fitted history (see interval_half_widths)."""
        self.interval_half_width = interval_half_widths(self.unfitted(), self.history, horizon)
        return self

    def forecast(self, horizon, future_indicators=None):
        """Month by month: each predicted month becomes an input for the next."""
        if future_indicators is None:
            future_indicators = hold_indicators(self.history, horizon)
        frame = with_future(self.history, future_indicators.iloc[:horizon])
        for month in frame.index[-horizon:]:
            row = make_features(frame.loc[:month], self.uses_indicators).iloc[[-1]]
            change = float(self.estimator.predict(row[self.feature_names])[0])
            frame.loc[month, TARGET_YOY] = change
            frame.loc[month, TARGET] = frame.loc[month - 12, TARGET] * (1 + change / 100)
        mean = frame[TARGET].iloc[-horizon:].to_numpy(dtype=float)
        if self.interval_half_width is None:
            lower = upper = np.full(horizon, np.nan)
        else:
            widths = self.interval_half_width
            width = np.array([widths[min(step, len(widths) - 1)] for step in range(horizon)])
            lower, upper = mean * (1 - width), mean * (1 + width)
        return pd.DataFrame({"mean": mean, "lower": lower, "upper": upper}, index=frame.index[-horizon:])

    def details(self):
        importance = self.estimator.feature_importances_
        total = float(importance.sum()) or 1.0
        ranked = sorted(zip(self.feature_names, importance), key=lambda item: -item[1])
        ranges = {}
        if self.uses_indicators:
            # The lowest and highest indicator values among the training features.
            # Outside this range a tree gives the same answer as at its edge.
            ranges = {"trained_range": {}}
            for column in INDICATORS:
                columns = [f"{column}_lag{lag}" for lag in INDICATOR_LAGS]
                ranges["trained_range"][column] = [
                    float(self.feature_range.loc["min", columns].min()),
                    float(self.feature_range.loc["max", columns].max()),
                ]
        return {
            "feature_importance": [
                {"feature": name, "importance": float(value) / total} for name, value in ranked
            ],
            **ranges,
        }


def _backtest(model: TreeForecaster, history: pd.DataFrame, origin: pd.Period, steps: int):
    """Forecast `steps` months from an earlier month; return (step, |relative error|) pairs."""
    predicted = model.fit(history.loc[:origin]).forecast(steps)["mean"].to_numpy()
    actual = history[TARGET].loc[origin + 1 : origin + steps].to_numpy(dtype=float)
    return [(step, abs(p / a - 1)) for step, (p, a) in enumerate(zip(predicted, actual))]


def interval_half_widths(
    model: TreeForecaster,
    history: pd.DataFrame,
    horizon: int = config.FORECAST_HORIZON,
    origins: int = config.INTERVAL_BACKTEST_ORIGINS,
    level: float = INTERVAL_LEVEL,
) -> list[float]:
    """Half-width of the prediction interval for each forecast month, as a share of the forecast.

    The model is refitted as of each of the preceding months and asked to
    forecast the months that are now known. For each band of forecast months
    (1-3, 4-6, ...) the half-width is the size that would have contained
    `level` of those past errors (a split-conformal quantile). Only months
    inside `history` are used, so nothing later can leak in. Widths never
    shrink as the forecast reaches further ahead.
    """
    last = history.index[-1]
    jobs = []
    for back in range(1, origins + 1):
        origin = last - back
        if len(history.loc[:origin]) < MIN_BACKTEST_HISTORY:
            break
        jobs.append((origin, min(horizon, back)))
    results = Parallel(n_jobs=-1)(
        delayed(_backtest)(model.unfitted(), history, origin, steps) for origin, steps in jobs
    )

    bands = math.ceil(horizon / INTERVAL_BAND_MONTHS)
    errors: list[list[float]] = [[] for _ in range(bands)]
    for result in results:
        for step, error in result:
            errors[step // INTERVAL_BAND_MONTHS].append(error)

    widths = []
    for band in errors:
        if not band:
            # No past forecast reached this far ahead; reuse the band before it.
            widths.append(widths[-1] if widths else float("nan"))
            continue
        ordered = sorted(band)
        rank = min(len(ordered), math.ceil((len(ordered) + 1) * level))
        widths.append(ordered[rank - 1])
    widths = np.maximum.accumulate(widths)
    return [float(widths[step // INTERVAL_BAND_MONTHS]) for step in range(horizon)]
