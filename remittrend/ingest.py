"""Parsers for the raw BSP and PSA files.

Each parser returns monthly data indexed by a pandas PeriodIndex (freq "M"),
covering everything in the file. Trimming to the study period happens in
dataset.py.
"""

import io
from pathlib import Path

import pandas as pd

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_NUMBER = {name: number for number, name in enumerate(MONTH_NAMES, start=1)}
MONTH_ABBREVIATION = {name[:3]: number for name, number in MONTH_NUMBER.items()}


def read_exchange_rate(path: Path) -> pd.DataFrame:
    """BSP peso per US dollar: monthly average and end-of-period rate.

    Reads the "monthly" sheet of the BSP workbook. The year is written only on
    each January row, so it is carried down to the other months.
    """
    workbook = pd.ExcelFile(path)
    sheet_name = next(
        (name for name in workbook.sheet_names if name.strip().lower() == "monthly"),
        None,
    )
    if sheet_name is None:
        raise ValueError(f"{path.name} has no 'monthly' sheet: {workbook.sheet_names}")

    sheet = workbook.parse(sheet_name, header=None, usecols="B:E")
    sheet.columns = ["year", "month", "average", "end_of_period"]
    sheet["year"] = pd.to_numeric(sheet["year"], errors="coerce").ffill()
    sheet["month"] = sheet["month"].astype("string").str.strip().map(MONTH_NUMBER)
    # Months without a published rate are blank or "n.a.".
    sheet["average"] = pd.to_numeric(sheet["average"], errors="coerce")
    sheet["end_of_period"] = pd.to_numeric(sheet["end_of_period"], errors="coerce")
    rows = sheet.dropna(subset=["year", "month", "average"])

    result = pd.DataFrame(
        {
            "php_per_usd_avg": rows["average"].to_numpy(dtype=float),
            "php_per_usd_eop": rows["end_of_period"].to_numpy(dtype=float),
        },
        index=pd.PeriodIndex.from_fields(
            year=rows["year"].astype(int), month=rows["month"].astype(int), freq="M"
        ),
    )
    result.index.name = "month"
    _require_consecutive_months(result.index, path)
    return result


def read_cpi_yoy(path: Path) -> pd.Series:
    """PSA year-on-year change of the all-items CPI for the Philippines, in percent.

    Reads the OpenSTAT export: a title line, then a semicolon-separated table
    with one column per month ("2019 Jan") and ".." for months not yet published.
    """
    lines = _read_text(path).splitlines()
    header = next(
        (i for i, line in enumerate(lines) if line.lstrip('"').startswith("Geolocation")),
        None,
    )
    if header is None:
        raise ValueError(f"{path.name} has no 'Geolocation' header row")

    table = pd.read_csv(io.StringIO("\n".join(lines[header:])), sep=";", na_values=[".."])
    geolocation = table["Geolocation"].str.strip().str.upper()
    commodity = table["Commodity Description"].str.strip().str.upper()
    match = table[(geolocation == "PHILIPPINES") & commodity.str.endswith("ALL ITEMS")]
    if len(match) != 1:
        raise ValueError(
            f"{path.name}: expected one PHILIPPINES / ALL ITEMS row, found {len(match)}"
        )

    values = match.iloc[0].drop(["Geolocation", "Commodity Description"])
    values = pd.to_numeric(values, errors="coerce").dropna()
    years, months = zip(*(_parse_month_label(label) for label in values.index))
    result = pd.Series(
        values.to_numpy(dtype=float),
        index=pd.PeriodIndex.from_fields(year=list(years), month=list(months), freq="M"),
        name="inflation_yoy_pct",
    )
    result.index.name = "month"
    _require_consecutive_months(result.index, path)
    return result


def read_remittances(path: Path) -> pd.DataFrame:
    """BSP monthly cash and personal remittances, in million US dollars.

    Reads the sheet that carries both series. Each year has a heading row
    ("2024", or "2025p" when the figures are preliminary) followed by one row
    per month. The value columns are found from the "Personal Remittances" and
    "Cash Remittances" headings, taking the first (levels) block of each.
    """
    workbook = pd.ExcelFile(path)
    sheet_name = next(
        (name for name in workbook.sheet_names if "personal" in name.lower()), None
    )
    if sheet_name is None:
        raise ValueError(f"{path.name} has no personal-remittances sheet: {workbook.sheet_names}")
    sheet = workbook.parse(sheet_name, header=None)

    personal_column = _find_heading_column(sheet, "Personal Remittances", path)
    cash_column = _find_heading_column(sheet, "Cash Remittances", path)

    records = []
    year, preliminary = None, False
    for row in sheet.itertuples(index=False):
        heading = _parse_year_heading(row[1])
        if heading is not None:
            year, preliminary = heading
            continue
        month = MONTH_NUMBER.get(str(row[4]).strip())
        if year is None or month is None:
            continue
        records.append(
            {
                "month": pd.Period(year=year, month=month, freq="M"),
                "cash_remittance_usd_million": pd.to_numeric(row[cash_column], errors="coerce"),
                "personal_remittance_usd_million": pd.to_numeric(
                    row[personal_column], errors="coerce"
                ),
                "preliminary": preliminary,
            }
        )

    result = pd.DataFrame.from_records(records).dropna(subset=["cash_remittance_usd_million"])
    result = result.set_index(pd.PeriodIndex(result.pop("month"), freq="M", name="month"))
    _require_consecutive_months(result.index, path)
    return result


def read_remittances_by_area(path: Path, first_year: int, last_year: int) -> pd.DataFrame:
    """BSP cash remittances by country and source, in million US dollars.

    The workbook has one sheet per year. Each area (the total, a region or a
    country) is a row, followed by a land-based row and a sea-based row. The
    sheets up to 2022 and the sheets from 2023 place the labels and the month
    columns differently and name the countries differently, so the columns are
    located from the "Country" heading and the row of month abbreviations.

    Returns one row per month and area: month, area, position, total,
    land_based, sea_based. Names are as written in the sheet, apart from
    footnote marks and letter-spacing ("A M E R I C A S"), which are removed.
    """
    workbook = pd.ExcelFile(path)
    frames = []
    for sheet_name in workbook.sheet_names:
        year_text = sheet_name.strip().split()[-1]
        if not (year_text.isdigit() and first_year <= int(year_text) <= last_year):
            continue
        frames.append(_read_area_sheet(workbook.parse(sheet_name, header=None), int(year_text), path))
    if not frames:
        raise ValueError(f"{path.name} has no sheets for {first_year} to {last_year}")
    return pd.concat(frames, ignore_index=True)


def _read_area_sheet(sheet: pd.DataFrame, year: int, path: Path) -> pd.DataFrame:
    label_column = None
    for _, row in sheet.head(20).iterrows():
        for column, cell in row.items():
            if isinstance(cell, str) and cell.strip() == "Country":
                label_column = column
    month_row, month_columns = None, {}
    for index, row in sheet.head(20).iterrows():
        found = {
            column: MONTH_ABBREVIATION[cell.strip()[:3].title()]
            for column, cell in row.items()
            if isinstance(cell, str) and cell.strip()[:3].title() in MONTH_ABBREVIATION
            and len(cell.strip()) <= 4
        }
        if len(found) == 12:
            month_row, month_columns = index, found
            break
    if label_column is None or month_row is None:
        raise ValueError(f"{path.name}, sheet for {year}: could not find the header rows")

    columns = list(month_columns)
    records = []
    area, position = None, 0
    for _, row in sheet.iloc[month_row + 1 :].iterrows():
        label = row[label_column]
        if not isinstance(label, str) or not label.strip():
            continue
        values = pd.to_numeric(row[columns], errors="coerce")
        source = _source_of(label)
        if source is None:
            if values.notna().sum() == 0:
                # A footnote, or an area with nothing reported this year.
                area = None
                continue
            area = _clean_area_name(label)
            position += 1
            source = "total"
        elif area is None:
            continue
        for column, value in values.items():
            records.append(
                {
                    "month": pd.Period(year=year, month=month_columns[column], freq="M"),
                    "area": area,
                    "position": position,
                    "source": source,
                    # The sheets are in thousand US dollars.
                    "value": value / 1000,
                }
            )

    long = pd.DataFrame.from_records(records)
    wide = long.pivot_table(
        index=["month", "area", "position"], columns="source", values="value", aggfunc="first"
    ).reset_index()
    wide.columns.name = None
    # Months with no total yet (the rest of the current year) are left out.
    grand_total = wide[wide["position"] == 1].dropna(subset=["total"])
    wide = wide[wide["month"].isin(grand_total["month"])].copy()
    for column in ("total", "land_based", "sea_based"):
        # A "." or blank within a published month means the value rounds off to zero.
        wide[column] = wide.get(column, 0.0)
        wide[column] = wide[column].fillna(0.0)
    return wide.sort_values(["month", "position"], ignore_index=True)


def _source_of(label: str) -> str | None:
    """'   Landbased' / 'Land-based' -> 'land_based'; an area name -> None."""
    key = label.strip().lower().replace("-", "").replace(" ", "")
    return {"landbased": "land_based", "seabased": "sea_based"}.get(key)


def _clean_area_name(label: str) -> str:
    name = " ".join(label.split())
    # Footnote marks: "TOTAL 1", "Others2".
    while name and name[-1].isdigit():
        name = name[:-1].rstrip()
    # Letter-spaced headings: "A M E R I C A S".
    parts = name.split(" ")
    if len(parts) > 2 and all(len(part) == 1 for part in parts):
        name = "".join(parts)
    return name


def _find_heading_column(sheet: pd.DataFrame, heading: str, path: Path) -> int:
    for _, row in sheet.head(10).iterrows():
        for column, cell in row.items():
            if isinstance(cell, str) and cell.strip().startswith(heading):
                return column
    raise ValueError(f"{path.name}: no '{heading}' heading in the first rows")


def _parse_year_heading(cell) -> tuple[int, bool] | None:
    """2024 -> (2024, False); '2025p' -> (2025, True); anything else -> None."""
    if isinstance(cell, (int, float)) and not pd.isna(cell) and 1900 <= cell <= 2100:
        return int(cell), False
    if isinstance(cell, str):
        text = cell.strip().lower().replace(" ", "")
        digits = text.rstrip("pr")
        if digits.isdigit() and len(digits) == 4:
            return int(digits), text.endswith("p")
    return None


def _parse_month_label(label: str) -> tuple[int, int]:
    """'2019 Jan' -> (2019, 1)"""
    year, month = label.split()
    return int(year), MONTH_ABBREVIATION[month[:3].title()]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1252")


def _require_consecutive_months(index: pd.PeriodIndex, path: Path) -> None:
    expected = pd.period_range(index[0], index[-1], freq="M")
    if not index.equals(expected):
        missing = expected.difference(index)
        raise ValueError(f"{path.name}: months are not consecutive, missing {list(missing[:6])}")
