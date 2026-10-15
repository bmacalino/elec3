"""Shared fixtures: the raw files parsed once per test run.

Tests that need a raw file are skipped when it is not in data/raw.
"""

import pandas as pd
import pytest

from remittrend import config, dataset, ingest

# The raw files the proposal was written from end in this month.
PROPOSAL_END = "2026-06"


def raw_path(key):
    path = next(r for r in config.RAW_INPUTS if r.key == key).find()
    if path is None:
        pytest.skip(f"raw file for '{key}' is not in data/raw")
    return path


def month(text):
    return pd.Period(text, freq="M")


@pytest.fixture(scope="session")
def exchange_rate():
    return ingest.read_exchange_rate(raw_path("exchange_rate"))


@pytest.fixture(scope="session")
def cpi_yoy():
    return ingest.read_cpi_yoy(raw_path("cpi"))


@pytest.fixture(scope="session")
def remittances():
    return ingest.read_remittances(raw_path("ofwp"))


@pytest.fixture(scope="session")
def months(remittances, exchange_rate, cpi_yoy):
    """The study period the pipeline would use for the files in data/raw."""
    return dataset.study_months(remittances, exchange_rate, cpi_yoy)


@pytest.fixture(scope="session")
def proposal_vintage(months):
    """For checks against figures quoted in the proposal.

    Those figures are for the files that end in June 2026. Once newer files are
    added, the study period grows and the BSP may revise its preliminary
    figures, so these checks are skipped instead of failing.
    """
    if str(months[-1]) != PROPOSAL_END:
        pytest.skip(f"the raw files now run to {months[-1]}; the proposal's figures are for {PROPOSAL_END}")


@pytest.fixture(scope="session")
def areas(months):
    return ingest.read_remittances_by_area(raw_path("ofw"), months[0].year, months[-1].year)


@pytest.fixture(scope="session")
def indicators(exchange_rate, cpi_yoy, months):
    return dataset.build_indicators(exchange_rate, cpi_yoy, months)


@pytest.fixture(scope="session")
def monthly(remittances, exchange_rate, cpi_yoy, months):
    return dataset.build_monthly(remittances, exchange_rate, cpi_yoy, months)


@pytest.fixture(scope="session")
def by_source(areas, months):
    return dataset.build_by_source(areas, months)


@pytest.fixture(scope="session")
def by_country(areas, months):
    return dataset.build_by_country(areas, months)
