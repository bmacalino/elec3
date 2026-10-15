"""Forecasting models and their evaluation.

The slow search for model settings is not run here; models are built with
fixed settings. The saved comparison is checked when the pipeline has been run.
"""

import numpy as np
import pandas as pd
import pytest

from remittrend import artifacts, config, evaluate, forecast
from remittrend.models import arima, ml
from remittrend.models.base import (
    EXCHANGE_RATE,
    TARGET,
    TARGET_YOY,
    SeasonalNaive,
    hold_indicators,
)
from tests.conftest import month

ORIGIN = month("2025-06")


def sarima(uses_indicators=False):
    key = "sarimax" if uses_indicators else "sarima"
    return arima.ArimaForecaster(key, key.upper(), (1, 0, 1), (1, 1, 0, 12), "c", uses_indicators)


def forest(uses_indicators=False):
    params = {"n_estimators": 50, "max_depth": 3, "min_samples_leaf": 3}
    return ml.TreeForecaster("rf", "Random Forest", "random_forest", params, uses_indicators)


def boosted(uses_indicators=False):
    params = {"n_estimators": 50, "max_depth": 2, "learning_rate": 0.1}
    return ml.TreeForecaster("xgb", "XGBoost", "xgboost", params, uses_indicators)


# ---- inputs ----

def test_held_indicators_carry_the_last_values_forward(monthly):
    history = monthly.loc[:ORIGIN]
    future = hold_indicators(history, 12)
    assert list(future.index) == list(pd.period_range("2025-07", "2026-06", freq="M"))
    assert (future[EXCHANGE_RATE] == history[EXCHANGE_RATE].iloc[-1]).all()
    assert (future["inflation_yoy_pct"] == history["inflation_yoy_pct"].iloc[-1]).all()
    # Year-on-year change of the held rate against the rate observed a year earlier.
    expected = (history[EXCHANGE_RATE].iloc[-1] / history.loc[month("2024-07"), EXCHANGE_RATE] - 1) * 100
    assert future.loc[month("2025-07"), "php_per_usd_yoy_pct"] == pytest.approx(expected)


def test_assumed_indicators_replace_the_held_values(monthly):
    future = hold_indicators(monthly.loc[:ORIGIN], 6, exchange_rate=60.0, inflation=4.0)
    assert (future[EXCHANGE_RATE] == 60.0).all()
    assert (future["inflation_yoy_pct"] == 4.0).all()


@pytest.mark.parametrize("uses_indicators", [False, True])
def test_features_use_only_earlier_months(monthly, uses_indicators):
    cut = month("2023-06")
    original = ml.make_features(monthly, uses_indicators)
    changed = monthly.copy()
    numeric = changed.columns.drop("preliminary")
    changed.loc[cut:, numeric] = changed.loc[cut:, numeric] * 3 + 100
    after = ml.make_features(changed, uses_indicators)
    # Features up to and including the cut month are unaffected by that month's own values.
    pd.testing.assert_frame_equal(original.loc[:cut], after.loc[:cut])
    assert not original.loc[cut + 1 :].equals(after.loc[cut + 1 :])


# ---- metrics and splits ----

def test_error_metrics():
    result = evaluate.error_metrics([100, 200, 400], [110, 180, 400])
    assert result["mae"] == pytest.approx(10)
    assert result["rmse"] == pytest.approx(np.sqrt((100 + 400 + 0) / 3))
    assert result["mape"] == pytest.approx((10 + 10 + 0) / 3)


def test_split_holds_out_the_latest_months(monthly):
    train, test = evaluate.split(monthly)
    assert len(test) == config.TEST_MONTHS
    assert test[-1] == monthly.index[-1]
    assert train[-1] + 1 == test[0]
    assert len(train) + len(test) == len(monthly)


def test_rolling_origins_end_at_the_main_split(monthly):
    origins = evaluate.rolling_origins(monthly)
    assert len(origins) == config.ROLLING_WINDOWS
    assert origins[-1] == evaluate.split(monthly)[0][-1]
    assert all(earlier + config.ROLLING_STEP == later for earlier, later in zip(origins, origins[1:]))


def test_rolling_origins_for_the_proposal_files(monthly, proposal_vintage):
    assert [str(o) for o in evaluate.rolling_origins(monthly)] == [
        "2023-06", "2023-12", "2024-06", "2024-12", "2025-06",
    ]


def test_diebold_mariano_separates_a_worse_model_from_an_equal_one():
    rng = np.random.default_rng(0)
    good = rng.normal(scale=10, size=60)
    similar = rng.normal(scale=10, size=60)
    worse = rng.normal(scale=40, size=60)

    equal = evaluate.diebold_mariano(similar, good, lags=11)
    assert equal["p_value"] > 0.05

    different = evaluate.diebold_mariano(worse, good, lags=11)
    assert different["p_value"] < 0.05
    assert different["statistic"] > 0  # positive: the first model has the larger errors
    # Swapping the models flips the sign and keeps the p-value.
    swapped = evaluate.diebold_mariano(good, worse, lags=11)
    assert swapped["statistic"] == pytest.approx(-different["statistic"])
    assert swapped["p_value"] == pytest.approx(different["p_value"])


# ---- models ----

def test_seasonal_naive_repeats_last_year(monthly):
    history = monthly.loc[:ORIGIN]
    predicted = SeasonalNaive().fit(history).forecast(14)
    assert predicted["mean"].iloc[0] == history.loc[month("2024-07"), TARGET]
    assert predicted["mean"].iloc[11] == history.loc[month("2025-06"), TARGET]
    # Beyond a year ahead it repeats its own forecast.
    assert predicted["mean"].iloc[12] == predicted["mean"].iloc[0]


def test_order_description():
    assert arima.describe_order((2, 1, 1), (0, 0, 0, 0), "c") == "ARIMA(2,1,1) with drift"
    assert arima.describe_order((1, 0, 1), (1, 1, 0, 12), "n") == "SARIMA(1,0,1)(1,1,0)[12]"
    assert arima.describe_order((1, 0, 0), (0, 0, 0, 0), "c") == "ARIMA(1,0,0) with constant"


def test_sarima_forecast_has_intervals_around_the_mean(monthly):
    predicted = sarima().fit(monthly.loc[:ORIGIN]).forecast(12)
    assert list(predicted.index) == list(pd.period_range("2025-07", "2026-06", freq="M"))
    assert (predicted["lower"] < predicted["mean"]).all()
    assert (predicted["mean"] < predicted["upper"]).all()
    # Intervals widen with the horizon.
    width = predicted["upper"] - predicted["lower"]
    assert width.iloc[-1] > width.iloc[0]


def test_assumptions_reach_sarimax_only_after_the_indicator_lag(monthly):
    history = monthly.loc[:ORIGIN]
    model = sarima(uses_indicators=True).fit(history)
    held = model.forecast(12)["mean"]
    assumed = model.forecast(12, hold_indicators(history, 12, exchange_rate=70.0, inflation=10.0))["mean"]
    lag = config.INDICATOR_LAG
    assert np.allclose(held.iloc[:lag], assumed.iloc[:lag])
    assert not np.allclose(held.iloc[lag:], assumed.iloc[lag:])
    # A model without indicators ignores the assumption.
    plain = sarima().fit(history)
    assert np.allclose(
        plain.forecast(12)["mean"],
        plain.forecast(12, hold_indicators(history, 12, exchange_rate=70.0, inflation=10.0))["mean"],
    )


@pytest.mark.parametrize("build", [forest, boosted])
@pytest.mark.parametrize("uses_indicators", [False, True])
def test_tree_models_forecast_in_us_dollars(monthly, build, uses_indicators):
    history = monthly.loc[:ORIGIN]
    model = build(uses_indicators).fit(history)
    predicted = model.forecast(12)
    assert len(predicted) == 12
    assert predicted["mean"].notna().all()
    assert predicted["lower"].isna().all()
    # Same scale as the series: within 25% of the same month a year earlier.
    last_year = history[TARGET].iloc[-12:].to_numpy()
    assert (np.abs(predicted["mean"].to_numpy() / last_year - 1) < 0.25).all()
    importance = model.details()["feature_importance"]
    assert sum(item["importance"] for item in importance) == pytest.approx(1)
    assert history[TARGET_YOY].notna().all()  # fitting and forecasting leave the history untouched


@pytest.mark.parametrize("build", [sarima, forest, boosted])
def test_evaluation_cannot_see_the_test_months(monthly, build):
    scrambled = monthly.copy()
    test_months = scrambled.loc[ORIGIN + 1 :].index
    scrambled.loc[test_months, [TARGET, TARGET_YOY]] = -999.0
    honest = evaluate.evaluate_at(build(), monthly, ORIGIN)
    blind = evaluate.evaluate_at(build(), scrambled, ORIGIN)
    assert np.allclose(honest["predicted"], blind["predicted"])


def test_evaluation_with_held_indicators_ignores_later_indicator_values(monthly):
    scrambled = monthly.copy()
    later = scrambled.loc[ORIGIN + 1 :].index
    scrambled.loc[later, [EXCHANGE_RATE, "php_per_usd_yoy_pct", "inflation_yoy_pct"]] = 999.0
    for build in (sarima, forest):
        honest = evaluate.evaluate_at(build(True), monthly, ORIGIN)
        blind = evaluate.evaluate_at(build(True), scrambled, ORIGIN)
        assert np.allclose(honest["predicted"], blind["predicted"])


def test_forecast_table_is_plain_lists(monthly):
    model = sarima().fit(monthly)
    table = forecast.forecast_table(model, 6)
    first = monthly.index[-1] + 1
    assert table["months"] == [str(first + step) for step in range(6)]
    assert all(isinstance(value, float) for value in table["mean"])


# ---- prediction intervals of the tree models ----

@pytest.fixture(scope="module")
def calibrated(monthly):
    """A small forest with intervals measured on the months up to the test split."""
    model = forest().fit(monthly.loc[:ORIGIN])
    model.interval_half_width = ml.interval_half_widths(model, model.history, horizon=12, origins=18)
    return model


def test_a_tree_model_has_no_interval_until_it_is_measured(monthly):
    model = forest().fit(monthly.loc[:ORIGIN])
    assert not model.has_intervals
    assert model.forecast(12)["lower"].isna().all()


def test_interval_widths_cover_every_month_and_never_shrink(calibrated):
    widths = calibrated.interval_half_width
    assert len(widths) == 12
    assert all(0 < width < 0.5 for width in widths)
    assert all(later >= earlier for earlier, later in zip(widths, widths[1:]))
    # One width per band of forecast months.
    band = ml.INTERVAL_BAND_MONTHS
    assert all(len(set(widths[start : start + band])) == 1 for start in range(0, 12, band))


def test_measured_interval_surrounds_the_forecast(calibrated, monthly):
    assert calibrated.has_intervals
    predicted = calibrated.forecast(12)
    assert (predicted["lower"] < predicted["mean"]).all()
    assert (predicted["mean"] < predicted["upper"]).all()
    scored = evaluate.forecast_at(calibrated, monthly, ORIGIN)
    assert scored["coverage"]["months"] == 12
    assert 0 <= scored["coverage"]["inside"] <= 12


def test_refitting_discards_an_interval_measured_on_other_data(calibrated, monthly):
    import copy

    refitted = copy.copy(calibrated).fit(monthly)
    assert not refitted.has_intervals
    assert calibrated.has_intervals


def test_interval_uses_only_the_history_it_is_given(monthly):
    history = monthly.loc[:ORIGIN]
    widths = ml.interval_half_widths(forest(), history, horizon=6, origins=8)
    scrambled = monthly.copy()
    scrambled.loc[ORIGIN + 1 :, [TARGET, TARGET_YOY]] = -999.0
    again = ml.interval_half_widths(forest(), scrambled.loc[:ORIGIN], horizon=6, origins=8)
    assert widths == again


def test_indicator_models_report_the_range_they_were_fitted_on(monthly):
    history = monthly.loc[:ORIGIN]
    for model in (forest(True), sarima(True)):
        trained = model.fit(history).details()["trained_range"]
        assert set(trained) == {"php_per_usd_yoy_pct", "inflation_yoy_pct"}
        for low, high in trained.values():
            assert low < high
        assert trained["inflation_yoy_pct"][1] == pytest.approx(history["inflation_yoy_pct"].max())


# ---- saved results ----

@pytest.fixture(scope="module")
def saved():
    paths = {out.key: out.path for out in config.OUTPUTS}
    if not (paths["metrics"].is_file() and paths["forecasts"].is_file()):
        pytest.skip("the pipeline has not been run")
    return artifacts.read_json(paths["metrics"]), artifacts.read_json(paths["forecasts"])


def test_saved_comparison_follows_the_selection_rule(saved):
    metrics, _ = saved
    rows = {row["key"]: row for row in metrics["models"]}
    candidates = [row for row in rows.values() if row["candidate"]]
    assert len(candidates) == 8
    assert not rows["seasonal_naive"]["candidate"]

    selection = metrics["selection"]
    assert selection["rule"] == config.MODEL_SELECTION
    assert selection["metric"] == ("rolling_rmse" if config.MODEL_SELECTION == "rolling" else "rmse")
    assert metrics["best_model"] == min(candidates, key=lambda row: row[selection["metric"]])["key"]
    assert metrics["best_on_test"] == min(candidates, key=lambda row: row["rmse"])["key"]
    assert metrics["best_on_rolling"] == min(candidates, key=lambda row: row["rolling_rmse"])["key"]

    for row in rows.values():
        assert len(row["predicted"]) == len(metrics["test"]["actual"]) == config.TEST_MONTHS
        scores = evaluate.error_metrics(metrics["test"]["actual"], row["predicted"])
        assert row["rmse"] == pytest.approx(scores["rmse"])
        assert len(row["rolling"]) == config.ROLLING_WINDOWS
        assert row["rolling_rmse"] == pytest.approx(
            sum(window["rmse"] for window in row["rolling"]) / config.ROLLING_WINDOWS
        )
        # The last window is the testing period itself.
        assert row["rolling"][-1]["rmse"] == pytest.approx(row["rmse"])
    for effect in metrics["indicator_effect"]:
        assert effect["improves"] == (effect["rmse_with"] < effect["rmse_without"])
        assert effect["improves_rolling"] == (effect["rolling_with"] < effect["rolling_without"])


def test_saved_comparison_tests_every_model_against_the_main_one(saved):
    metrics, _ = saved
    for row in metrics["models"]:
        if row["key"] == metrics["best_model"]:
            assert row["versus_best"] is None
        else:
            assert 0 <= row["versus_best"]["p_value"] <= 1
            assert row["versus_best"]["different"] == (row["versus_best"]["p_value"] < 0.05)


def test_saved_comparison_has_an_interval_for_every_candidate(saved):
    metrics, forecasts = saved
    for row in metrics["models"]:
        if not row["candidate"]:
            assert row["coverage"] is None
            continue
        assert row["has_intervals"]
        assert row["interval_method"] == ("model" if row["family"] == "statistical" else "backtest")
        assert row["coverage"]["months"] == config.TEST_MONTHS
        inside = sum(
            low <= actual <= high
            for low, actual, high in zip(row["lower"], metrics["test"]["actual"], row["upper"])
        )
        assert row["coverage"]["inside"] == inside
    for table in forecasts["models"].values():
        assert all(low < mean < high for low, mean, high in zip(table["lower"], table["mean"], table["upper"]))


def test_saved_forecasts_cover_every_model(saved, monthly):
    metrics, forecasts = saved
    candidates = {row["key"] for row in metrics["models"] if row["candidate"]}
    assert set(forecasts["models"]) == candidates
    assert len(forecasts["months"]) == config.FORECAST_HORIZON
    assert forecasts["months"][0] == str(monthly.index[-1] + 1)
    for table in forecasts["models"].values():
        assert len(table["mean"]) == config.FORECAST_HORIZON
        assert all(value is not None and value > 0 for value in table["mean"])
    assert set(forecasts["trained_range"]) == {key for key in candidates if key.endswith("x")}
