"""Exports the results as tables and figures for the paper, and records how they were produced.

Tables are written as CSV and figures as PNG in the `paper` folder. They are
built from the same files the dashboard reads, so the paper and the dashboard
show the same numbers.
"""

import hashlib
import platform
import zipfile
from datetime import datetime
from importlib import metadata
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from remittrend import artifacts, config, dataset, ingest, relationship, trend
from remittrend.models.base import EXCHANGE_RATE, TARGET, TARGET_YOY
from remittrend.seasonality import MONTH_LABELS

OUTPUTS = {out.key: out.path for out in config.OUTPUTS}

# Colours of the dashboard's light theme (frontend/src/index.css).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
NEUTRAL, INK, MUTED, GRID = "#c3c2b7", "#0b0b0b", "#52514e", "#e1e0d9"
PAGE_WIDTH = 6.5  # inches: the text width of a letter or A4 page
USD = "US$ million"

PACKAGES = ("pandas", "numpy", "scipy", "statsmodels", "scikit-learn", "xgboost", "matplotlib",
            "flask", "plotly", "joblib", "openpyxl", "xlrd")


def load() -> dict:
    """Everything the pipeline has produced."""
    return {
        "monthly": dataset.read_monthly(),
        "by_source": dataset.read_csv(OUTPUTS["by_source"]).set_index("month"),
        "by_country": dataset.read_csv(OUTPUTS["by_country"]),
        "analysis": artifacts.read_json(OUTPUTS["analysis"]),
        "metrics": artifacts.read_json(OUTPUTS["metrics"]),
        "forecasts": artifacts.read_json(OUTPUTS["forecasts"]),
    }


# ---- tables ----

def tables(data: dict | None = None) -> dict[str, pd.DataFrame]:
    """The result tables, keyed by file name (without .csv)."""
    data = data or load()
    monthly, analysis, metrics, forecasts = (
        data["monthly"], data["analysis"], data["metrics"], data["forecasts"]
    )
    related = analysis["relationship"]
    rows = {row["key"]: row for row in metrics["models"]}
    best = metrics["best_model"]
    order = sorted(metrics["models"], key=lambda row: row[metrics["selection"]["metric"]])
    cash = monthly[TARGET]

    summary = []
    for column, label in relationship.SERIES_LABELS.items():
        series = monthly[column]
        summary.append({
            "series": label, "months": len(series), "mean": series.mean(), "std_dev": series.std(),
            "minimum": series.min(), "minimum_month": str(series.idxmin()),
            "maximum": series.max(), "maximum_month": str(series.idxmax()),
            "first": series.iloc[0], "last": series.iloc[-1],
        })

    yearly = []
    for year, values in cash.groupby(cash.index.year):
        earlier = cash[(cash.index.year == year - 1) & cash.index.month.isin(values.index.month)]
        yearly.append({
            "year": year, "months": len(values), "total_usd_million": values.sum(),
            "average_usd_million": values.mean(),
            "change_from_same_months_of_previous_year_pct":
                (values.sum() / earlier.sum() - 1) * 100 if len(earlier) == len(values) else None,
        })

    stationarity = []
    for row in related["stationarity"]:
        for form, key in (("as it is", "level"), ("first difference", "first_difference")):
            result = row[key]
            stationarity.append({
                "series": row["label"], "form": form,
                "adf_statistic": result["adf"]["statistic"], "adf_p_value": result["adf"]["p_value"],
                "kpss_statistic": result["kpss"]["statistic"], "kpss_p_value": result["kpss"]["p_value"],
                "verdict": result["verdict"],
                "used_in_relationship_tests": (row["differencing"] == 1) == (key == "first_difference"),
            })

    check_labels = {
        "recent": "{start} to {end}",
        "undifferenced": "{start} to {end}, indicators not differenced where ADF and KPSS disagree",
    }
    samples = [(f"{related['study_period'][0]} to {related['study_period'][1]}", related["indicators"])] + [
        (check_labels[item["key"]].format(**item), item["indicators"]) for item in related["checks"]
    ]
    correlations = [
        {"sample": sample, "indicator": item["label"], "lag_months": row["lag"],
         "correlation": row["correlation"], "p_value": row["p_value"],
         "observations": row["observations"], "significant": row["significant"]}
        for sample, items in samples for item in items for row in item["correlations"]
    ]
    granger = [
        {"sample": sample, "indicator": item["label"], "lags": row["lags"],
         "f_statistic": row["f_statistic"], "p_value": row["p_value"], "significant": row["significant"]}
        for sample, items in samples for item in items for row in item["granger"]
    ]

    comparison = []
    for row in order:
        versus = row["versus_best"] or {}
        coverage = row["coverage"]
        comparison.append({
            "model": row["name"], "family": row["family"], "main_model": row["key"] == best,
            "uses_indicators": row["uses_indicators"], "settings": row["spec"],
            "training_rows": row["training_rows"],
            "test_mae": row["mae"], "test_rmse": row["rmse"], "test_mape_pct": row["mape"],
            "rolling_rmse": row["rolling_rmse"],
            "dm_p_value_vs_main": versus.get("p_value"),
            "differs_from_main": versus.get("different"),
            "interval": row["interval_method"],
            "test_months_inside_interval": f"{coverage['inside']} of {coverage['months']}" if coverage else None,
        })

    rolling = [
        {"model": row["name"], "data_to": window["origin"], "rmse": window["rmse"],
         "mae": window["mae"], "mape_pct": window["mape"], "settings": window["spec"]}
        for row in order for window in row["rolling"]
    ]
    effect = [
        {"without_indicators": rows[e["without"]]["name"], "with_indicators": rows[e["with"]]["name"],
         "test_rmse_without": e["rmse_without"], "test_rmse_with": e["rmse_with"],
         "rolling_rmse_without": e["rolling_without"], "rolling_rmse_with": e["rolling_with"],
         "lower_error_on_test": e["improves"], "lower_error_on_rolling": e["improves_rolling"]}
        for e in metrics["indicator_effect"]
    ]

    predictions = pd.DataFrame({"month": metrics["test"]["months"], "actual": metrics["test"]["actual"]})
    for row in order:
        predictions[row["name"]] = row["predicted"]

    forecast = pd.DataFrame({"month": forecasts["months"]})
    forecast[f"{rows[best]['name']} (main model)"] = forecasts["models"][best]["mean"]
    forecast["main_model_lower_95"] = forecasts["models"][best]["lower"]
    forecast["main_model_upper_95"] = forecasts["models"][best]["upper"]
    for row in order:
        if row["candidate"] and row["key"] != best:
            forecast[row["name"]] = forecasts["models"][row["key"]]["mean"]

    by_source = data["by_source"]
    sources = by_source.groupby(by_source.index.year).agg(
        months=("cash_remittance_usd_million", "size"),
        land_based_usd_million=("land_based_usd_million", "sum"),
        sea_based_usd_million=("sea_based_usd_million", "sum"),
        total_usd_million=("cash_remittance_usd_million", "sum"),
    )
    sources["sea_based_share_pct"] = sources["sea_based_usd_million"] / sources["total_usd_million"] * 100
    sources = sources.rename_axis("year").reset_index()

    by_country = data["by_country"]
    complete = sources.loc[sources["months"] == 12, "year"].max()
    in_year = by_country[by_country["month"].dt.year == complete]
    countries = (
        in_year.groupby("country")[["cash_remittance_usd_million", "land_based_usd_million",
                                    "sea_based_usd_million"]].sum()
        .sort_values("cash_remittance_usd_million", ascending=False)
    )
    countries["share_pct"] = countries["cash_remittance_usd_million"] / countries["cash_remittance_usd_million"].sum() * 100
    countries = countries.head(15).rename_axis("country").reset_index()
    countries.insert(0, "rank", range(1, len(countries) + 1))
    countries.insert(1, "year", complete)

    return {
        "01_dataset_summary": pd.DataFrame(summary),
        "02_yearly_totals": pd.DataFrame(yearly),
        "03_seasonal_profile": pd.DataFrame(analysis["seasonality"]["profile"]),
        "04_stationarity_tests": pd.DataFrame(stationarity),
        "05_lagged_correlations": pd.DataFrame(correlations),
        "06_granger_tests": pd.DataFrame(granger),
        "07_model_comparison": pd.DataFrame(comparison),
        "08_rolling_windows": pd.DataFrame(rolling),
        "09_indicator_effect": pd.DataFrame(effect),
        "10_test_predictions": predictions,
        "11_forecast": forecast,
        "12_sources_by_year": sources,
        "13_top_countries": countries,
    }


# ---- figures ----

def _axes(figure: Figure, rows=1, columns=1, **options):
    axes = figure.subplots(rows, columns, squeeze=False, **options)
    for ax in axes.flat:
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(NEUTRAL)
        ax.tick_params(colors=MUTED, labelsize=8, length=3)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    return axes


def _thousands(axis) -> None:
    """Tick labels with thousands separators: 3,400 rather than 3400."""
    axis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))


def _figure(height: float) -> Figure:
    return Figure(figsize=(PAGE_WIDTH, height), dpi=300, layout="constrained")


def _dates(months) -> list:
    return [pd.Period(month, freq="M").to_timestamp() for month in months]


def _legend(ax, **options):
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, **options)


def figures(data: dict | None = None) -> dict[str, Figure]:
    """The figures, keyed by file name (without .png)."""
    data = data or load()
    monthly, analysis, metrics, forecasts = (
        data["monthly"], data["analysis"], data["metrics"], data["forecasts"]
    )
    seasonal = analysis["seasonality"]
    related = analysis["relationship"]
    rows = {row["key"]: row for row in metrics["models"]}
    best = rows[metrics["best_model"]]
    cash = monthly[TARGET]
    x = _dates(monthly.index)
    result = {}

    # 1. The series and its trend.
    figure = _figure(3.0)
    ax = _axes(figure)[0, 0]
    ax.plot(x, cash, color=NEUTRAL, linewidth=1, label="Monthly")
    ax.plot(x, trend.moving_averages(cash)["ma_12"], color=BLUE, linewidth=2, label="12-month average")
    ax.set_ylabel(USD, fontsize=8, color=MUTED)
    _thousands(ax.yaxis)
    _legend(ax, loc="upper left", ncols=2)
    result["01_remittances_and_trend"] = figure

    # 2. Seasonal index, drawn from the baseline of 100.
    figure = _figure(2.8)
    ax = _axes(figure)[0, 0]
    index = [row["seasonal_index"] for row in seasonal["profile"]]
    bars = ax.bar(MONTH_LABELS, [value - 100 for value in index], bottom=100, width=0.65,
                  color=[BLUE if value > 100 else NEUTRAL for value in index])
    ax.bar_label(bars, labels=[f"{value:.1f}" for value in index], fontsize=7, color=MUTED, padding=2)
    ax.axhline(100, color=NEUTRAL, linewidth=0.8)
    ax.set_ylabel("Seasonal index (100 = ordinary month)", fontsize=8, color=MUTED)
    ax.margins(y=0.15)
    result["02_seasonal_index"] = figure

    # 3. STL decomposition.
    parts = seasonal["decomposition"]
    figure = _figure(5.6)
    axes = _axes(figure, 4, 1, sharex=True)
    panels = (("observed", "Observed", INK), ("trend", "Trend", BLUE),
              ("seasonal", "Seasonal", ORANGE), ("residual", "Remainder", AQUA))
    for ax, (key, title, color) in zip(axes.flat, panels):
        ax.plot(_dates(parts["months"]), parts[key], color=color, linewidth=1.3)
        ax.set_title(title, fontsize=8.5, loc="left", color=INK)
        ax.set_ylabel(USD, fontsize=7, color=MUTED)
        _thousands(ax.yaxis)
    result["03_decomposition"] = figure

    # 4. The three series on a year-on-year basis.
    figure = _figure(4.6)
    axes = _axes(figure, 3, 1, sharex=True)
    panels = ((TARGET_YOY, "Cash remittances, change from a year earlier (%)", BLUE),
              ("php_per_usd_yoy_pct", "Peso per US dollar, change from a year earlier (%)", ORANGE),
              ("inflation_yoy_pct", "Inflation rate (%)", AQUA))
    for ax, (column, title, color) in zip(axes.flat, panels):
        ax.plot(x, monthly[column], color=color, linewidth=1.5)
        ax.axhline(0, color=NEUTRAL, linewidth=0.8)
        ax.set_title(title, fontsize=8.5, loc="left", color=INK)
    result["04_indicators"] = figure

    # 5. Lagged correlations.
    figure = _figure(2.6)
    axes = _axes(figure, 1, 3, sharey=True)
    threshold = 1.96 / (len(monthly) - 1) ** 0.5
    for ax, item in zip(axes.flat, related["indicators"]):
        values = [row["correlation"] for row in item["correlations"]]
        ax.bar(range(len(values)), values, width=0.65,
               color=[BLUE if row["significant"] else NEUTRAL for row in item["correlations"]])
        for level in (threshold, -threshold):
            ax.axhline(level, color=MUTED, linewidth=0.7, linestyle=":")
        ax.axhline(0, color=NEUTRAL, linewidth=0.8)
        ax.set_title(item["label"].replace(", ", ",\n", 1), fontsize=7.5, loc="left", color=INK)
        ax.set_xlabel("Months the indicator leads", fontsize=7, color=MUTED)
        ax.set_xticks(range(0, len(values), 3))
        ax.set_ylim(-0.5, 0.5)
    axes[0, 0].set_ylabel("Correlation", fontsize=8, color=MUTED)
    result["05_lagged_correlations"] = figure

    # 6. Model errors.
    metric = metrics["selection"]["metric"]
    ranked = sorted(metrics["models"], key=lambda row: row[metric])
    figure = _figure(3.0)
    ax = _axes(figure)[0, 0]
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    bars = ax.barh([row["name"] for row in ranked], [row[metric] for row in ranked], height=0.6,
                   color=[BLUE if row["key"] == best["key"] else NEUTRAL for row in ranked])
    ax.bar_label(bars, labels=[f"{row[metric]:.1f}" for row in ranked], fontsize=7, color=MUTED, padding=3)
    ax.invert_yaxis()
    label = "RMSE averaged over the test windows" if metric == "rolling_rmse" else "RMSE on the test months"
    ax.set_xlabel(f"{label} ({USD})", fontsize=8, color=MUTED)
    ax.margins(x=0.1)
    result["06_model_errors"] = figure

    # 7. Actual against predicted on the test months.
    test = metrics["test"]
    figure = _figure(3.0)
    ax = _axes(figure)[0, 0]
    months = _dates(test["months"])
    if best["lower"][0] is not None:
        ax.fill_between(months, best["lower"], best["upper"], color=BLUE, alpha=0.18, linewidth=0,
                        label="95% prediction interval")
    ax.plot(months, test["actual"], color=INK, linewidth=1.8, marker="o", markersize=4, label="Actual")
    ax.plot(months, best["predicted"], color=BLUE, linewidth=1.8, marker="o", markersize=4,
            label=best["name"])
    ax.set_ylabel(USD, fontsize=8, color=MUTED)
    _thousands(ax.yaxis)
    _legend(ax, loc="upper left")
    result["07_actual_vs_predicted"] = figure

    # 8. The forecast.
    table = forecasts["models"][best["key"]]
    recent = cash.iloc[-36:]
    figure = _figure(3.0)
    ax = _axes(figure)[0, 0]
    ahead = _dates(forecasts["months"])
    if table["lower"][0] is not None:
        ax.fill_between(ahead, table["lower"], table["upper"], color=ORANGE, alpha=0.18, linewidth=0,
                        label="95% prediction interval")
    ax.plot(_dates(recent.index), recent, color=BLUE, linewidth=1.8, label="Observed")
    ax.plot([_dates(recent.index)[-1], *ahead], [recent.iloc[-1], *table["mean"]], color=ORANGE,
            linewidth=1.8, label=f"Forecast ({best['name']})")
    ax.set_ylabel(USD, fontsize=8, color=MUTED)
    _thousands(ax.yaxis)
    _legend(ax, loc="upper left", ncols=3)
    result["08_forecast"] = figure
    return result


def export(directory: Path = config.PAPER_DIR) -> tuple[list[Path], list[Path]]:
    """Write every table as CSV and every figure as PNG."""
    data = load()
    table_dir, figure_dir = directory / "tables", directory / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    table_paths = []
    for name, table in tables(data).items():
        path = table_dir / f"{name}.csv"
        table.to_csv(path, index=False, float_format="%.4f")
        table_paths.append(path)
    figure_paths = []
    for name, figure in figures(data).items():
        path = figure_dir / f"{name}.png"
        figure.savefig(path, facecolor="white")
        figure_paths.append(path)
    return table_paths, figure_paths


# ---- manifest ----

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workbook_last_saved(path: Path) -> str | None:
    """When an Excel workbook was last saved, from the file's own properties.

    For a file kept as downloaded this is when its publisher last updated it,
    which dates the figures better than the day it was downloaded.
    """
    if path.suffix.lower() != ".xlsx":
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("docProps/core.xml"))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return None
    modified = root.find("{http://purl.org/dc/terms/}modified")
    return modified.text if modified is not None else None


def _coverage(key: str, path: Path) -> list[str] | None:
    """First and last month with a value in a raw file."""
    if key == "ofwp":
        index = ingest.read_remittances(path).index
    elif key == "exchange_rate":
        index = ingest.read_exchange_rate(path).index
    elif key == "cpi":
        index = ingest.read_cpi_yoy(path).index
    else:
        return None
    return [str(index[0]), str(index[-1])]


def write_manifest(path: Path = config.MANIFEST_PATH) -> dict:
    """Record the data, settings and software behind the current results."""
    monthly = dataset.read_monthly()
    metrics = artifacts.read_json(OUTPUTS["metrics"])
    best = next(row for row in metrics["models"] if row["key"] == metrics["best_model"])

    raw_files = []
    for item in config.RAW_INPUTS:
        found = item.find()
        if found is None:
            continue
        raw_files.append({
            "dataset": item.label,
            "source": item.source,
            "file": found.name,
            "bytes": found.stat().st_size,
            "sha256": _sha256(found),
            "workbook_last_saved": _workbook_last_saved(found),
            "copied_to_this_folder": datetime.fromtimestamp(found.stat().st_mtime).isoformat(timespec="seconds"),
            "covers": _coverage(item.key, found),
        })

    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None

    manifest = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "study_period": {
            "start": str(monthly.index[0]),
            "end": str(monthly.index[-1]),
            "months": int(len(monthly)),
            "end_set_by": "STUDY_END in config.py" if config.STUDY_END else "latest month in all three series",
            "preliminary_from": str(monthly.index[monthly["preliminary"]].min())
            if monthly["preliminary"].any() else None,
        },
        "split": metrics["split"],
        "test_windows_data_to": metrics["rolling_origins"],
        "main_model": {
            "key": best["key"], "name": best["name"], "settings": best["spec"],
            "rule": metrics["selection"]["description"],
        },
        "settings": {
            name: getattr(config, name)
            for name in ("STUDY_START", "STUDY_END", "TEST_MONTHS", "FORECAST_HORIZON", "INDICATOR_LAG",
                         "ROLLING_WINDOWS", "ROLLING_STEP", "MODEL_SELECTION",
                         "INTERVAL_BACKTEST_ORIGINS", "RELATIONSHIP_RECENT_START",
                         "SEASONAL_PERIOD", "RANDOM_SEED", "TREND_STABLE_BAND_PCT")
        },
        "raw_files": raw_files,
        "outputs": [
            {"file": out.relative_path, "sha256": _sha256(out.path)}
            for out in config.OUTPUTS if out.path.is_file()
        ],
        "software": {"python": platform.python_version(), "platform": platform.platform(), **versions},
        "last_values": {
            "month": str(monthly.index[-1]),
            "cash_remittance_usd_million": float(monthly[TARGET].iloc[-1]),
            EXCHANGE_RATE: float(monthly[EXCHANGE_RATE].iloc[-1]),
            "inflation_yoy_pct": float(monthly["inflation_yoy_pct"].iloc[-1]),
        },
    }
    artifacts.write_json(path, manifest)
    return manifest
