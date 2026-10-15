"""Builds the tables for the study period from the parsed raw files."""

import pandas as pd

from remittrend import config, countries


def year_on_year_pct(series: pd.Series) -> pd.Series:
    """(value in the month / value in the same month a year earlier - 1) x 100.

    The series must have consecutive months, as the parsers in ingest.py guarantee.
    """
    return (series / series.shift(12) - 1) * 100


def study_months(
    remittances: pd.DataFrame, exchange_rate: pd.DataFrame, cpi_yoy: pd.Series
) -> pd.PeriodIndex:
    """The months of the study period.

    It starts at config.STUDY_START. Unless config.STUDY_END freezes it, it ends
    at the latest month for which all three series have a value, so adding a
    month to the raw files extends the period.
    """
    available = min(
        remittances["cash_remittance_usd_million"].dropna().index.max(),
        exchange_rate["php_per_usd_avg"].dropna().index.max(),
        cpi_yoy.dropna().index.max(),
    )
    end = pd.Period(config.STUDY_END, freq="M") if config.STUDY_END else available
    if end > available:
        raise ValueError(
            f"STUDY_END is {end}, but the raw files have all three series only to {available}"
        )
    return pd.period_range(config.STUDY_START, end, freq="M")


def build_indicators(
    exchange_rate: pd.DataFrame, cpi_yoy: pd.Series, months: pd.PeriodIndex
) -> pd.DataFrame:
    """Exchange rate, its year-on-year change, and inflation for the study months.

    The year-on-year change is computed before trimming, so the first year uses
    the rates of the year before as its base.
    """
    average = exchange_rate["php_per_usd_avg"]
    indicators = pd.DataFrame(
        {
            "php_per_usd_avg": average,
            "php_per_usd_yoy_pct": year_on_year_pct(average),
            "inflation_yoy_pct": cpi_yoy,
        }
    ).reindex(months)
    indicators.index.name = "month"
    _require_complete(indicators, "Indicators")
    return indicators


def build_monthly(
    remittances: pd.DataFrame,
    exchange_rate: pd.DataFrame,
    cpi_yoy: pd.Series,
    months: pd.PeriodIndex,
) -> pd.DataFrame:
    """The main dataset: one row per study month.

    Columns: cash_remittance_usd_million, cash_remittance_yoy_pct,
    php_per_usd_avg, php_per_usd_yoy_pct, inflation_yoy_pct, preliminary. Both
    year-on-year changes are computed before trimming, so the first year has values.
    """
    indicators = build_indicators(exchange_rate, cpi_yoy, months)
    cash_yoy = year_on_year_pct(remittances["cash_remittance_usd_million"]).reindex(months)
    remit = remittances.reindex(months)
    monthly = pd.DataFrame(
        {
            "cash_remittance_usd_million": remit["cash_remittance_usd_million"],
            "cash_remittance_yoy_pct": cash_yoy,
            "php_per_usd_avg": indicators["php_per_usd_avg"],
            "php_per_usd_yoy_pct": indicators["php_per_usd_yoy_pct"],
            "inflation_yoy_pct": indicators["inflation_yoy_pct"],
            "preliminary": remit["preliminary"],
        }
    )
    monthly.index.name = "month"
    _require_complete(monthly, "The monthly dataset")
    monthly["preliminary"] = monthly["preliminary"].astype(bool)
    return monthly


def build_by_source(areas: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    """Total cash remittances split into land-based and sea-based, per study month."""
    total = areas[areas["position"] == 1].set_index("month")
    by_source = pd.DataFrame(
        {
            "cash_remittance_usd_million": total["total"],
            "land_based_usd_million": total["land_based"],
            "sea_based_usd_million": total["sea_based"],
        }
    ).reindex(months)
    by_source.index.name = "month"
    _require_complete(by_source, "Remittances by source")
    return by_source


def build_by_country(areas: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    """Cash remittances per study month and country, under the current BSP names.

    Region and sub-group rows are left out, so the countries of a month add up
    to that month's total.
    """
    rows = areas[areas["month"].isin(months) & ~areas["area"].map(countries.is_aggregate)]
    by_country = (
        rows.assign(country=rows["area"].map(countries.current_name))
        .groupby(["month", "country"], as_index=False)[["total", "land_based", "sea_based"]]
        .sum()
        .rename(
            columns={
                "total": "cash_remittance_usd_million",
                "land_based": "land_based_usd_million",
                "sea_based": "sea_based_usd_million",
            }
        )
    )
    return by_country.sort_values(
        ["month", "cash_remittance_usd_million"], ascending=[True, False], ignore_index=True
    )


def write_csv(table: pd.DataFrame, path) -> None:
    """Write a table with its month as the first day of the month (YYYY-MM-DD)."""
    out = table.reset_index() if table.index.name == "month" else table.copy()
    out["month"] = pd.PeriodIndex(out["month"], freq="M").to_timestamp().strftime("%Y-%m-%d")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def read_csv(path) -> pd.DataFrame:
    """Read a table written by write_csv, with month as a monthly Period column."""
    table = pd.read_csv(path)
    table["month"] = pd.PeriodIndex(table["month"], freq="M")
    return table


def read_monthly(path=None) -> pd.DataFrame:
    """The main dataset as written by the ingest stage, indexed by month."""
    path = path or next(out.path for out in config.OUTPUTS if out.key == "monthly")
    return read_csv(path).set_index("month")


def _require_complete(table: pd.DataFrame, what: str) -> None:
    incomplete = table[table.isna().any(axis=1)]
    if not incomplete.empty:
        raise ValueError(
            f"{what} has missing values for: " + ", ".join(str(m) for m in incomplete.index[:6])
        )
