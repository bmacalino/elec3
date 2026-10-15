"""Builds, compares and saves the forecasting models.

Every model's settings (ARIMA orders, tree hyperparameters) are chosen only on
the months before the window it is tested on. The models are compared on
several 12-month windows, the main model is chosen, and all models are then
refitted on every month to forecast the months ahead.
"""

import copy

import joblib
import pandas as pd

from remittrend import config, evaluate
from remittrend.models.arima import ArimaForecaster, select_order
from remittrend.models.base import (
    EXCHANGE_RATE,
    INTERVAL_LEVEL,
    TARGET,
    Forecaster,
    SeasonalNaive,
    hold_indicators,
)
from remittrend.models.ml import TreeForecaster, tune

# Each model without the indicators, and the same model with them.
PAIRS = (("arima", "arimax"), ("sarima", "sarimax"), ("rf", "rf_x"), ("xgb", "xgb_x"))
SELECTION_RULES = {
    "rolling": "Lowest RMSE averaged over the {windows} test windows",
    "test": "Lowest RMSE on the testing period",
}
SIGNIFICANCE = 0.05


def build_models(train: pd.DataFrame) -> list[Forecaster]:
    """The eight candidate models, with settings chosen on the given months."""
    models: list[Forecaster] = []
    for seasonal, key, name in ((False, "arima", "ARIMA"), (True, "sarima", "SARIMA")):
        chosen = select_order(train[TARGET], seasonal=seasonal)
        orders = (chosen["order"], chosen["seasonal_order"], chosen["trend"])
        models.append(ArimaForecaster(key, name, *orders))
        models.append(ArimaForecaster(f"{key}x", f"{name}X", *orders, uses_indicators=True))
    for kind, key, name in (("random_forest", "rf", "Random Forest"), ("xgboost", "xgb", "XGBoost")):
        models.append(TreeForecaster(key, name, kind, tune(train, kind, False)))
        models.append(
            TreeForecaster(f"{key}_x", f"{name} with indicators", kind, tune(train, kind, True), True)
        )
    return models


def _fit(model: Forecaster, history: pd.DataFrame, calibrate: bool) -> Forecaster:
    fitted = copy.copy(model).fit(history)
    if calibrate and isinstance(fitted, TreeForecaster):
        fitted.calibrate()
    return fitted


def compare(monthly: pd.DataFrame, progress=lambda message: None) -> tuple[dict, list[Forecaster]]:
    """Score every model on each test window and choose the main model.

    Returns the comparison and the models whose settings were chosen on the
    main training period, which are the ones refitted for forecasting.
    """
    train_months, test_months = evaluate.split(monthly)
    origins = evaluate.rolling_origins(monthly)
    main_origin = origins[-1]

    # 1. Every window: settings chosen on the months up to its origin, then scored.
    windows: dict[str, list[dict]] = {}
    main_models: list[Forecaster] = []
    for origin in origins:
        progress(f"  window ending {origin + config.FORECAST_HORIZON}: choosing settings on data to {origin}")
        models = build_models(monthly.loc[:origin])
        if origin == main_origin:
            main_models = models
        for model in [*models, SeasonalNaive()]:
            result = evaluate.evaluate_at(copy.copy(model), monthly, origin)
            windows.setdefault(model.key, []).append(
                {key: result[key] for key in ("origin", "mae", "rmse", "mape", "errors")}
                | {"spec": model.spec}
            )

    # 2. The testing period in detail, with prediction intervals.
    progress("  measuring prediction intervals on the training months")
    history = monthly.loc[:main_origin]
    rows = []
    for model in [*main_models, SeasonalNaive()]:
        fitted = _fit(model, history, calibrate=True)
        main = evaluate.forecast_at(fitted, monthly, main_origin)
        row = {
            "key": model.key,
            "name": model.name,
            "family": model.family,
            "candidate": model.family != "reference",
            "uses_indicators": model.uses_indicators,
            "has_intervals": bool(fitted.has_intervals),
            "interval_method": fitted.interval_method if fitted.has_intervals else None,
            "spec": model.spec,
            "training_rows": getattr(fitted, "training_rows", len(train_months)),
            **{key: main[key] for key in ("mae", "rmse", "mape", "predicted", "lower", "upper")},
            "coverage": main.get("coverage"),
            **fitted.details(),
        }
        if model.uses_indicators:
            actual = evaluate.forecast_at(fitted, monthly, main_origin, indicators="actual")
            row["with_actual_indicators"] = {
                key: actual[key] for key in ("mae", "rmse", "mape", "predicted")
            }
        row["rolling"] = [
            {key: window[key] for key in ("origin", "mae", "rmse", "mape", "spec")}
            for window in windows[model.key]
        ]
        row["rolling_rmse"] = sum(w["rmse"] for w in windows[model.key]) / len(origins)
        rows.append(row)

    # 3. The main model, and whether the others differ from it by more than chance.
    metric = "rolling_rmse" if config.MODEL_SELECTION == "rolling" else "rmse"
    best = min((row for row in rows if row["candidate"]), key=lambda row: row[metric])
    pooled = {key: [e for window in results for e in window["errors"]] for key, results in windows.items()}
    for row in rows:
        if row["key"] == best["key"]:
            row["versus_best"] = None
            continue
        test = evaluate.diebold_mariano(
            pooled[row["key"]], pooled[best["key"]], lags=config.FORECAST_HORIZON - 1
        )
        row["versus_best"] = test | {
            "different": test["p_value"] is not None and test["p_value"] < SIGNIFICANCE
        }

    by_key = {row["key"]: row for row in rows}
    comparison = {
        "selection": {
            "rule": config.MODEL_SELECTION,
            "metric": metric,
            "description": SELECTION_RULES[config.MODEL_SELECTION].format(windows=len(origins)),
            "forecasts_compared": len(pooled[best["key"]]),
            "significance": SIGNIFICANCE,
        },
        "best_model": best["key"],
        "best_on_test": min((r for r in rows if r["candidate"]), key=lambda r: r["rmse"])["key"],
        "best_on_rolling": min((r for r in rows if r["candidate"]), key=lambda r: r["rolling_rmse"])["key"],
        "split": {
            "train_start": str(train_months[0]),
            "train_end": str(train_months[-1]),
            "test_start": str(test_months[0]),
            "test_end": str(test_months[-1]),
        },
        "indicator_lag": config.INDICATOR_LAG,
        "interval_level": INTERVAL_LEVEL,
        "interval_backtests": config.INTERVAL_BACKTEST_ORIGINS,
        "test": {
            "months": [str(month) for month in test_months],
            "actual": monthly.loc[test_months, TARGET].tolist(),
        },
        "rolling_origins": [str(o) for o in origins],
        "models": rows,
        "indicator_effect": [
            {
                "without": without,
                "with": with_,
                "rmse_without": by_key[without]["rmse"],
                "rmse_with": by_key[with_]["rmse"],
                "improves": by_key[with_]["rmse"] < by_key[without]["rmse"],
                "rolling_without": by_key[without]["rolling_rmse"],
                "rolling_with": by_key[with_]["rolling_rmse"],
                "improves_rolling": by_key[with_]["rolling_rmse"] < by_key[without]["rolling_rmse"],
            }
            for without, with_ in PAIRS
        ],
    }
    return comparison, main_models


def fit_all(monthly: pd.DataFrame, models: list[Forecaster]) -> list[Forecaster]:
    """Each model refitted on every month, ready to forecast the months ahead."""
    return [_fit(model, monthly, calibrate=True) for model in models]


def forecast_table(model: Forecaster, horizon: int, exchange_rate=None, inflation=None) -> dict:
    """A fitted model's forecast as plain lists, under an optional what-if assumption."""
    future = hold_indicators(model.history, horizon, exchange_rate, inflation)
    predicted = model.forecast(horizon, future)
    return {
        "months": [str(month) for month in predicted.index],
        "mean": predicted["mean"].tolist(),
        "lower": predicted["lower"].tolist(),
        "upper": predicted["upper"].tolist(),
        # The indicator values the model was given, to compare with its training range.
        "indicators": {column: future[column].tolist() for column in future.columns},
    }


def default_forecasts(fitted: list[Forecaster], horizon: int = config.FORECAST_HORIZON) -> dict:
    """Forecasts from every model with the indicators held at their last observed values."""
    history = fitted[0].history
    tables = {model.key: forecast_table(model, horizon) for model in fitted}
    return {
        "last_observed": str(history.index[-1]),
        "horizon": horizon,
        "months": next(iter(tables.values()))["months"],
        "assumptions": {
            EXCHANGE_RATE: float(history[EXCHANGE_RATE].iloc[-1]),
            "inflation_yoy_pct": float(history["inflation_yoy_pct"].iloc[-1]),
        },
        "models": {
            key: {name: table[name] for name in ("mean", "lower", "upper")}
            for key, table in tables.items()
        },
        "trained_range": {
            model.key: model.details().get("trained_range") for model in fitted if model.uses_indicators
        },
    }


def save_models(fitted: list[Forecaster], directory=config.MODELS_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for model in fitted:
        joblib.dump(model, directory / f"{model.key}.joblib")


def load_model(key: str, directory=config.MODELS_DIR) -> Forecaster:
    return joblib.load(directory / f"{key}.joblib")
