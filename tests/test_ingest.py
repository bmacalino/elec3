"""Checks the parsers against the real raw files and the figures in the proposal."""

import pandas as pd
import pytest

from remittrend import config, ingest
from tests.conftest import month


def test_exchange_rate_covers_2018_base_year_and_study_period(exchange_rate, months):
    assert exchange_rate.index.min() <= month("2018-01")
    assert exchange_rate.index.max() >= months[-1]
    assert exchange_rate.index.is_unique


def test_exchange_rate_annual_averages_match_proposal(exchange_rate, proposal_vintage):
    # Proposal: about 54.48 pesos per US dollar in 2022 and about 57.51 in 2025.
    average = exchange_rate["php_per_usd_avg"]
    yearly = average.groupby(average.index.year).mean()
    assert yearly[2022] == pytest.approx(54.48, abs=0.01)
    assert yearly[2025] == pytest.approx(57.51, abs=0.01)


def test_inflation_matches_proposal(cpi_yoy, proposal_vintage):
    assert cpi_yoy.index.min() == month("2019-01")
    assert cpi_yoy[month("2023-01")] == 8.7
    assert cpi_yoy[month("2025-07")] == 0.9
    assert cpi_yoy[month("2026-02")] == 2.4
    assert cpi_yoy[month("2026-04")] == 7.2


def test_remittances_match_proposal(remittances, proposal_vintage):
    # Proposal: US$34.49 billion in 2024 and US$35.63 billion in 2025;
    # US$2.81 billion in November 2024 and US$3.38 billion in December 2024;
    # personal remittances of US$39.62 billion in 2025.
    cash = remittances["cash_remittance_usd_million"]
    yearly = cash.groupby(cash.index.year).sum()
    assert yearly[2024] == pytest.approx(34_490, abs=5)
    assert yearly[2025] == pytest.approx(35_630, abs=5)
    assert cash[month("2024-11")] == pytest.approx(2_810, abs=5)
    assert cash[month("2024-12")] == pytest.approx(3_380, abs=5)
    personal = remittances["personal_remittance_usd_million"]
    assert personal[personal.index.year == 2025].sum() == pytest.approx(39_620, abs=5)


def test_remittances_cover_study_period_and_flag_preliminary_years(remittances, months):
    assert remittances.index.min() <= month(config.STUDY_START)
    assert remittances.index.max() >= months[-1]
    # The latest years are published as preliminary; earlier ones are final.
    assert not remittances.loc[month("2019-01"), "preliminary"]
    assert remittances["preliminary"].iloc[-1]


def test_by_area_total_equals_the_monthly_workbook(areas, remittances, months):
    total = areas[areas["position"] == 1].set_index("month")["total"]
    cash = remittances["cash_remittance_usd_million"].reindex(months)
    assert list(total.index) == list(months)
    assert (total - cash).abs().max() < 1e-6


def test_by_area_sources_add_up(areas):
    difference = areas["land_based"] + areas["sea_based"] - areas["total"]
    assert difference.abs().max() < 1e-6


def test_parsers_agree_with_the_hand_cleaned_file(exchange_rate, cpi_yoy, proposal_vintage):
    path = config.REFERENCE_DIR / "Merge_exogenous_inflation_fx_monthly.csv"
    if not path.is_file():
        pytest.skip("reference file is not in data/reference")
    reference = pd.read_csv(path)
    reference.index = pd.PeriodIndex(reference["month"], freq="M")

    average = exchange_rate["php_per_usd_avg"].reindex(reference.index).round(4)
    inflation = cpi_yoy.reindex(reference.index)
    assert (average - reference["php_per_usd_avg"]).abs().max() == pytest.approx(0)
    assert (inflation - reference["inflation_yoy_pct"]).abs().max() == pytest.approx(0)


def test_gap_in_months_is_rejected(tmp_path):
    path = tmp_path / "cpi.csv"
    path.write_text(
        '"Title"\n\n'
        '"Geolocation";"Commodity Description";"2019 Jan";"2019 Feb";"2019 Mar"\n'
        '"PHILIPPINES";"0 - ALL ITEMS";4.4;..;3.4\n'
    )
    with pytest.raises(ValueError, match="not consecutive"):
        ingest.read_cpi_yoy(path)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        (2024, (2024, False)),
        (2024.0, (2024, False)),
        ("2025p", (2025, True)),
        (" 2026 p ", (2026, True)),
        ("2023r", (2023, False)),
        ("January", None),
        (None, None),
        (3379.8, None),
    ],
)
def test_year_heading(cell, expected):
    assert ingest._parse_year_heading(cell) == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("TOTAL 1", "TOTAL"),
        ("Others2", "Others"),
        ("A M E R I C A S", "AMERICAS"),
        ("MIDDLE  EAST", "MIDDLE EAST"),
        ("Papua New  Guinea", "Papua New Guinea"),
        ("Korea, Rep. of", "Korea, Rep. of"),
    ],
)
def test_area_name_cleaning(label, expected):
    assert ingest._clean_area_name(label) == expected


def test_source_rows_are_recognised():
    assert ingest._source_of("   Landbased") == "land_based"
    assert ingest._source_of("Sea-based") == "sea_based"
    assert ingest._source_of("Singapore") is None
