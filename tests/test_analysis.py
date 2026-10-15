"""Trend, seasonality and relationship functions, on made-up series with known answers
and on the real dataset."""

import json

import numpy as np
import pandas as pd
import pytest

from remittrend import artifacts, config, relationship, seasonality, trend
from tests.conftest import month


def monthly_index(periods, start="2015-01"):
    return pd.period_range(start, periods=periods, freq="M")


# A fixed seasonal pattern that averages exactly 1.
FACTORS = np.array([1.02, 0.94, 0.97, 0.88, 0.90, 1.00, 1.08, 1.00, 1.03, 1.07, 0.96, 1.15])


def seasonal_series(years=8, growth_per_year=0.03):
    index = monthly_index(years * 12)
    level = 1000 * (1 + growth_per_year) ** (np.arange(len(index)) / 12)
    return pd.Series(level * np.tile(FACTORS, years), index=index)


# ---- trend ----

def test_percent_changes_on_real_data(monthly, proposal_vintage):
    cash = monthly["cash_remittance_usd_million"]
    changes = trend.percent_changes(cash)
    expected = (cash[month("2024-12")] / cash[month("2024-11")] - 1) * 100
    assert changes.loc[month("2024-12"), "mom_pct"] == pytest.approx(expected)
    assert changes.loc[month("2024-12"), "mom_pct"] == pytest.approx(20.35, abs=0.01)
    assert changes.loc[month("2024-12"), "yoy_pct"] == pytest.approx(
        (cash[month("2024-12")] / cash[month("2023-12")] - 1) * 100
    )


def test_year_to_date_restarts_each_january(monthly):
    cash = monthly["cash_remittance_usd_million"]
    ytd = trend.year_to_date(cash)
    assert ytd[month("2025-01")] == pytest.approx(cash[month("2025-01")])
    assert ytd[month("2025-12")] == pytest.approx(cash[cash.index.year == 2025].sum())


@pytest.mark.parametrize(
    ("growth", "expected"),
    [(0.05, "rising"), (0.0, "stable"), (0.005, "stable"), (-0.04, "falling")],
)
def test_trend_direction_ignores_the_seasonal_cycle(growth, expected):
    series = seasonal_series(growth_per_year=growth)
    result = trend.classify_trend(series, "2016-06", "2021-11", band_pct=1.0)
    assert result["direction"] == expected
    assert result["annual_change_pct"] == pytest.approx(growth * 100, abs=0.2)


def test_trend_direction_needs_two_smoothed_points():
    series = seasonal_series()
    assert trend.classify_trend(series, "2015-01", "2015-06")["direction"] is None


def test_period_summary(monthly, proposal_vintage):
    cash = monthly["cash_remittance_usd_million"]
    summary = trend.period_summary(cash, "2025-01", "2025-12")
    assert summary["months"] == 12
    assert summary["total"] == pytest.approx(35_630, abs=5)
    assert summary["highest_month"] == "2025-12"


# ---- seasonality ----

def test_centred_moving_average():
    constant = pd.Series(5.0, index=monthly_index(36))
    centred = seasonality.centred_moving_average(constant)
    assert centred.isna().sum() == 12
    assert centred.dropna().eq(5.0).all()
    assert centred.index[centred.notna()][0] == month("2015-07")


def test_seasonal_index_recovers_a_known_pattern():
    profile = seasonality.monthly_profile(seasonal_series())
    assert list(profile["month"]) == list(range(1, 13))
    assert profile["seasonal_index"].mean() == pytest.approx(100)
    assert np.allclose(profile["seasonal_index"], FACTORS * 100, atol=0.3)
    assert profile.loc[profile["rank"] == 1, "label"].item() == "Dec"


def test_seasonal_index_is_not_inflated_by_a_half_year():
    full = seasonality.monthly_profile(seasonal_series(years=8))
    partial = seasonality.monthly_profile(seasonal_series(years=8).iloc[:-6])
    assert np.allclose(full["seasonal_index"], partial["seasonal_index"], atol=0.3)


def test_decomposition_adds_up_and_december_is_the_peak(monthly, proposal_vintage):
    cash = monthly["cash_remittance_usd_million"]
    parts = seasonality.decompose(cash)
    rebuilt = parts["trend"] + parts["seasonal"] + parts["residual"]
    assert np.allclose(rebuilt, parts["observed"])
    assert 0 < seasonality.seasonal_strength(parts) < 1

    result = seasonality.analyse(cash)
    assert result["highest_months"][0] == "Dec"
    assert len(result["profile"]) == 12
    assert result["by_year"]["years"] == list(range(2019, 2027))
    # 2026 has data to June only.
    assert result["by_year"]["values"][-1][6:] == [None] * 6


# ---- relationship ----

def test_adf_tells_noise_from_a_random_walk():
    rng = np.random.default_rng(0)
    noise = pd.Series(rng.normal(size=200))
    assert relationship.adf_test(noise)["stationary"]
    assert not relationship.adf_test(noise.cumsum())["stationary"]


def test_lagged_correlation_and_granger_find_a_known_lag():
    rng = np.random.default_rng(1)
    indicator = pd.Series(rng.normal(size=160))
    target = 0.8 * indicator.shift(3) + pd.Series(rng.normal(scale=0.4, size=160))

    correlations = relationship.lagged_correlations(target, indicator)
    strongest = max(correlations, key=lambda row: abs(row["correlation"]))
    assert strongest["lag"] == 3
    assert strongest["significant"]

    granger = {row["lags"]: row["significant"] for row in relationship.granger_tests(target, indicator)}
    assert granger[3] and granger[6]


def test_kpss_agrees_with_adf_on_clear_cases():
    rng = np.random.default_rng(0)
    noise = pd.Series(rng.normal(size=200))
    assert relationship.stationarity(noise)["verdict"] == "stationary"
    assert relationship.stationarity(noise.cumsum())["verdict"] == "not stationary"


@pytest.fixture(scope="module")
def related(monthly):
    return relationship.analyse(monthly)


def test_relationship_analysis_of_real_data(related):
    assert [item["series"] for item in related["indicators"]] == list(relationship.INDICATORS)
    for item in related["indicators"]:
        assert len(item["correlations"]) == relationship.MAX_CORRELATION_LAG + 1
        assert len(item["granger"]) == relationship.MAX_GRANGER_LAG
    by_series = {row["series"]: row for row in related["stationarity"]}
    # Remittances in dollars trend upward; both tests agree they are not stationary.
    assert by_series["cash_remittance_usd_million"]["differencing"] == 1
    assert by_series["cash_remittance_usd_million"]["level"]["verdict"] == "not stationary"
    for row in related["stationarity"]:
        # The ADF test decides the differencing; KPSS is reported beside it.
        assert row["differencing"] == (0 if row["level"]["adf"]["stationary"] else 1)
        assert 0.01 <= row["level"]["kpss"]["p_value"] <= 0.1


def test_relationship_checks_reuse_the_same_tests(related, monthly):
    checks = {item["key"]: item for item in related["checks"]}
    assert set(checks) == {"recent", "undifferenced"}

    recent = checks["recent"]
    assert recent["start"] == config.RELATIONSHIP_RECENT_START
    assert recent["end"] == str(monthly.index[-1])
    assert recent["months"] == len(monthly.loc[config.RELATIONSHIP_RECENT_START :])
    # Fewer months, so fewer observations behind each correlation.
    assert (
        recent["indicators"][0]["correlations"][0]["observations"]
        < related["indicators"][0]["correlations"][0]["observations"]
    )

    undifferenced = checks["undifferenced"]
    disputed = {
        row["series"] for row in related["stationarity"]
        if row["differencing"] == 1 and row["level"]["verdict"] == "tests disagree"
    }
    assert set(undifferenced["series"]) == disputed
    for item in undifferenced["indicators"]:
        assert item["differencing"] == (0 if item["series"] in disputed else 1)


def test_indicator_overlap_matches_proposal(related, proposal_vintage):
    assert related["indicator_overlap"]["correlation"] == pytest.approx(0.69, abs=0.01)


# ---- artifacts ----

def test_json_writer_handles_numpy_and_missing_values(tmp_path):
    value = {
        "a": np.float64(1.5),
        "b": np.nan,
        "c": np.int64(3),
        "d": [np.bool_(True), month("2025-01")],
        "e": pd.Series([1.0, np.nan]),
    }
    path = tmp_path / "out.json"
    artifacts.write_json(path, value)
    assert json.loads(path.read_text()) == {
        "a": 1.5,
        "b": None,
        "c": 3,
        "d": [True, "2025-01"],
        "e": [1.0, None],
    }
