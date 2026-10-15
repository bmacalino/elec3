"""Checks the tables built for the study period against the proposal's figures."""

import pandas as pd
import pytest

from remittrend import config, countries, dataset
from tests.conftest import month


# ---- the study period ----

def test_study_period_ends_where_all_three_series_have_data(remittances, exchange_rate, cpi_yoy, months):
    assert str(months[0]) == config.STUDY_START
    assert months[-1] == min(remittances.index.max(), exchange_rate.index.max(), cpi_yoy.index.max())
    assert len(months) == len(pd.period_range(months[0], months[-1], freq="M"))


def test_study_period_is_90_months_for_the_proposal_files(months, proposal_vintage):
    assert len(months) == 90
    assert str(months[-1]) == "2026-06"


def test_a_new_month_in_the_raw_files_extends_the_period(remittances, exchange_rate, cpi_yoy, months):
    next_month = months[-1] + 1
    extended = remittances.reindex(remittances.index.append(pd.PeriodIndex([next_month], freq="M")))
    extended.loc[next_month] = remittances.iloc[-1]
    longer = dataset.study_months(extended, exchange_rate, cpi_yoy)
    if next_month <= min(exchange_rate.index.max(), cpi_yoy.index.max()):
        assert longer[-1] == next_month
    else:
        assert longer[-1] == months[-1]


def test_study_end_can_be_frozen(remittances, exchange_rate, cpi_yoy, monkeypatch):
    monkeypatch.setattr(config, "STUDY_END", "2025-12")
    frozen = dataset.study_months(remittances, exchange_rate, cpi_yoy)
    assert str(frozen[-1]) == "2025-12"
    assert len(frozen) == 84

    monkeypatch.setattr(config, "STUDY_END", "2035-01")
    with pytest.raises(ValueError, match="STUDY_END"):
        dataset.study_months(remittances, exchange_rate, cpi_yoy)


# ---- indicators ----

def test_indicators_cover_the_study_months(indicators, months):
    assert list(indicators.index) == list(months)
    assert not indicators.isna().any().any()


def test_year_on_year_change_uses_same_month_a_year_earlier(exchange_rate, indicators):
    average = exchange_rate["php_per_usd_avg"]
    expected = (average[month("2019-01")] / average[month("2018-01")] - 1) * 100
    assert indicators.loc[month("2019-01"), "php_per_usd_yoy_pct"] == pytest.approx(expected)


def test_exchange_rate_change_and_inflation_correlation_matches_proposal(indicators, proposal_vintage):
    # Proposal: the two have a correlation of about 0.69.
    correlation = indicators["php_per_usd_yoy_pct"].corr(indicators["inflation_yoy_pct"])
    assert correlation == pytest.approx(0.69, abs=0.01)


# ---- the monthly dataset ----

def test_monthly_has_complete_rows(monthly, months):
    assert list(monthly.index) == list(months)
    assert list(monthly.columns) == [
        "cash_remittance_usd_million",
        "cash_remittance_yoy_pct",
        "php_per_usd_avg",
        "php_per_usd_yoy_pct",
        "inflation_yoy_pct",
        "preliminary",
    ]
    assert not monthly.isna().any().any()
    assert monthly["preliminary"].dtype == bool


def test_remittance_year_on_year_change(monthly, remittances):
    cash = remittances["cash_remittance_usd_million"]
    expected = (cash[month("2019-01")] / cash[month("2018-01")] - 1) * 100
    assert monthly.loc[month("2019-01"), "cash_remittance_yoy_pct"] == pytest.approx(expected)


def test_monthly_agrees_with_the_group_dataset(monthly, proposal_vintage):
    path = config.REFERENCE_DIR / "remittrend_monthly_dataset_v2.xlsx"
    if not path.is_file():
        pytest.skip("reference file is not in data/reference")
    reference = pd.read_excel(path)
    reference.index = pd.PeriodIndex(reference["month"], freq="M")
    assert list(reference.index) == list(monthly.index)
    # The reference is rounded: 4 decimals for levels, 2 for the change, 1 for inflation.
    for column, tolerance in [
        ("cash_remittance_usd_million", 0.00011),
        ("php_per_usd_avg", 0.00011),
        ("php_per_usd_yoy_pct", 0.0051),
        ("inflation_yoy_pct", 1e-9),
    ]:
        assert (monthly[column] - reference[column]).abs().max() < tolerance, column
    assert (monthly["preliminary"] == reference["preliminary"].astype(bool)).all()


# ---- sources and countries ----

def test_sources_add_up_to_the_total(by_source, monthly):
    total = by_source["land_based_usd_million"] + by_source["sea_based_usd_million"]
    assert (total - monthly["cash_remittance_usd_million"]).abs().max() < 1e-6


def test_sources_match_proposal(by_source, proposal_vintage):
    # Proposal: in 2025, US$28.49 billion land-based and US$7.14 billion sea-based.
    year = by_source[by_source.index.year == 2025].sum()
    assert year["land_based_usd_million"] == pytest.approx(28_490, abs=5)
    assert year["sea_based_usd_million"] == pytest.approx(7_140, abs=5)


def test_countries_add_up_to_the_total_every_month(by_country, monthly):
    sums = by_country.groupby("month")["cash_remittance_usd_million"].sum()
    assert (sums - monthly["cash_remittance_usd_million"]).abs().max() < 1e-6


def test_country_shares_match_proposal(by_country, proposal_vintage):
    # Proposal: in 2025 the United States had 39.7%, Singapore 7.3%, Saudi Arabia 6.6%.
    year = by_country[by_country["month"].dt.year == 2025]
    totals = year.groupby("country")["cash_remittance_usd_million"].sum()
    share = totals / totals.sum() * 100
    assert share["United States of America"] == pytest.approx(39.7, abs=0.05)
    assert share["Singapore"] == pytest.approx(7.3, abs=0.06)
    assert share["Saudi Arabia"] == pytest.approx(6.6, abs=0.05)
    assert list(share.sort_values(ascending=False).index[:3]) == [
        "United States of America",
        "Singapore",
        "Saudi Arabia",
    ]


def test_no_region_rows_among_countries(by_country):
    names = set(by_country["country"])
    assert not any(countries.is_aggregate(name) for name in names)
    assert not names & set(countries.RENAMED) - set(countries.RENAMED.values())


def test_main_countries_have_one_series_across_the_2023_name_change(by_country, months):
    counts = by_country.groupby("country")["month"].nunique()
    for name in [
        "United States of America",
        "Singapore",
        "Saudi Arabia",
        "Japan",
        "United Kingdom",
        "United Arab Emirates",
        "Canada",
        "Qatar",
        "Taiwan, Republic of China",
        "Hong Kong, SAR China",
        "Korea (South)",
    ]:
        assert counts[name] == len(months), name


def test_csv_round_trip(monthly, tmp_path):
    path = tmp_path / "monthly.csv"
    dataset.write_csv(monthly, path)
    assert path.read_text().splitlines()[1].startswith("2019-01-01,")
    back = dataset.read_monthly(path)
    pd.testing.assert_frame_equal(back, monthly, check_freq=False)
