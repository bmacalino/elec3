"""Builds the content of each dashboard page from what the pipeline produced."""

import io

import pandas as pd

from app import figures
from remittrend import artifacts, config, dataset, trend
from remittrend import forecast as forecasting
from remittrend.models.base import EXCHANGE_RATE, TARGET, TARGET_YOY, hold_indicators

OUTPUTS = {out.key: out for out in config.OUTPUTS}
HORIZONS = (3, 6, 12)
HISTORY_MONTHS_ON_FORECAST_CHART = 36
TOP_COUNTRIES = 10
INTERVAL_LABEL = "95% prediction interval"


class NotReady(Exception):
    """Files the page needs have not been produced yet."""

    def __init__(self, missing: list[str]):
        super().__init__("Run the pipeline first")
        self.missing = missing


class BadRequest(ValueError):
    """A query parameter is not usable."""


# ---- loading ----

_cache: dict = {}


def _cached(path, read):
    """Read a file once, and again only when it changes (the pipeline was re-run)."""
    stamp = path.stat().st_mtime_ns
    hit = _cache.get(path)
    if hit is None or hit[0] != stamp:
        hit = (stamp, read(path))
        _cache[path] = hit
    return hit[1]


def _read_output(path):
    if path.suffix == ".json":
        return artifacts.read_json(path)
    table = dataset.read_csv(path)
    return table if "country" in table.columns else table.set_index("month")


def _require(*keys: str) -> list:
    missing = [OUTPUTS[key].relative_path for key in keys if not OUTPUTS[key].path.is_file()]
    if missing:
        raise NotReady(missing)
    return [_cached(OUTPUTS[key].path, _read_output) for key in keys]


def _model(key: str):
    path = config.MODELS_DIR / f"{key}.joblib"
    if not path.is_file():
        raise NotReady([path.relative_to(config.ROOT).as_posix()])
    return _cached(path, lambda p: forecasting.load_model(key, p.parent))


def pipeline_status() -> dict:
    """Which raw files are in data/raw and which pipeline outputs exist."""
    raw = []
    for item in config.RAW_INPUTS:
        found = item.find()
        raw.append(
            {
                "key": item.key,
                "label": item.label,
                "source": item.source,
                "expected": item.patterns[0],
                "found": found.name if found else None,
            }
        )
    outputs = [
        {"key": out.key, "path": out.relative_path, "exists": out.path.is_file()}
        for out in config.OUTPUTS
    ]
    return {"raw": raw, "outputs": outputs}


# ---- small helpers ----

def _long(month: pd.Period) -> str:
    return month.strftime("%B %Y")


def _span(first: pd.Period, last: pd.Period) -> str:
    """'January–June 2026', or 'July 2025–June 2026' across years."""
    if first == last:
        return _long(first)
    if first.year == last.year:
        return f"{first.strftime('%B')}–{last.strftime('%B %Y')}"
    return f"{_long(first)}–{_long(last)}"


def _period_range(monthly: pd.DataFrame, start: str | None, end: str | None) -> tuple[pd.Period, pd.Period]:
    first, last = monthly.index[0], monthly.index[-1]
    try:
        begin = pd.Period(start, freq="M") if start else first
        finish = pd.Period(end, freq="M") if end else last
    except ValueError as error:
        raise BadRequest("Months must be written as YYYY-MM.") from error
    if not (first <= begin <= finish <= last):
        raise BadRequest(f"Choose months from {first} to {last}, with the start before the end.")
    return begin, finish


def _range_info(monthly, begin, finish) -> dict:
    return {
        "min": str(monthly.index[0]),
        "max": str(monthly.index[-1]),
        "start": str(begin),
        "end": str(finish),
        "label": _span(begin, finish),
    }


def _delta(value: float, unit: str, text: str, *, good_when_up: bool | None = True) -> dict:
    """A change shown under a figure. good_when_up=None marks it as neither good nor bad."""
    direction = "flat" if abs(value) < 0.05 else ("up" if value > 0 else "down")
    if good_when_up is None or direction == "flat":
        tone = "neutral"
    else:
        tone = "good" if (direction == "up") == good_when_up else "bad"
    return {"value": float(value), "unit": unit, "direction": direction, "tone": tone, "text": text}


def _pct(new: float, old: float) -> float:
    return (new / old - 1) * 100


def _model_rows(metrics: dict) -> dict:
    return {row["key"]: row for row in metrics["models"]}


# ---- overview ----

def overview() -> dict:
    monthly, forecasts, metrics, analysis = _require("monthly", "forecasts", "metrics", "analysis")
    cash = monthly[TARGET]
    latest, previous = cash.index[-1], cash.index[-2]
    year_ago = latest - 12
    models = _model_rows(metrics)
    best = models[metrics["best_model"]]
    preliminary = bool(monthly["preliminary"].iloc[-1])

    this_year = cash[cash.index.year == latest.year]
    last_year_same_months = cash[(cash.index.year == latest.year - 1) & (cash.index.month <= latest.month)]
    next_month = pd.Period(forecasts["months"][0], freq="M")
    next_value = forecasts["models"][best["key"]]["mean"][0]
    next_range = [forecasts["models"][best["key"]][bound][0] for bound in ("lower", "upper")]
    rate = monthly[EXCHANGE_RATE]
    inflation = monthly["inflation_yoy_pct"]
    mom = _pct(cash[latest], cash[previous])
    yoy = float(monthly[TARGET_YOY].iloc[-1])

    kpis = [
        {
            "key": "latest",
            "title": "Cash remittances",
            "caption": _long(latest) + (", preliminary" if preliminary else ""),
            "value": float(cash[latest]),
            "unit": "usd_million",
            "delta": _delta(mom, "percent", f"from {_long(previous)}"),
        },
        {
            "key": "mom",
            "title": "Change from last month",
            "caption": f"{_long(latest)} against {_long(previous)}",
            "value": mom,
            "unit": "percent_change",
            "delta": _delta(float(cash[latest] - cash[previous]), "usd_million", "in US dollars"),
        },
        {
            "key": "yoy",
            "title": "Change from last year",
            "caption": f"{_long(latest)} against {_long(year_ago)}",
            "value": yoy,
            "unit": "percent_change",
            "delta": _delta(float(cash[latest] - cash[year_ago]), "usd_million", "in US dollars"),
        },
        {
            "key": "ytd",
            "title": "Year to date",
            "caption": _span(this_year.index[0], latest),
            "value": float(this_year.sum()),
            "unit": "usd_million",
            "delta": _delta(
                _pct(this_year.sum(), last_year_same_months.sum()),
                "percent",
                f"from the same months of {latest.year - 1}",
            ),
        },
        {
            "key": "next",
            "title": "Forecast for next month",
            "caption": f"{_long(next_month)}, {best['name']}",
            "value": float(next_value),
            "unit": "usd_million",
            "delta": _delta(
                _pct(next_value, cash[next_month - 12]), "percent", f"from {_long(next_month - 12)}"
            ),
            # The 95% prediction interval, where the model has one.
            "range": (
                {"lower": next_range[0], "upper": next_range[1]} if next_range[0] is not None else None
            ),
        },
        {
            "key": "exchange_rate",
            "title": "Peso per US dollar",
            "caption": f"{_long(latest)}, monthly average",
            "value": float(rate[latest]),
            "unit": "peso",
            "delta": _delta(
                _pct(rate[latest], rate[previous]), "percent", f"from {_long(previous)}",
                good_when_up=None,
            ),
        },
        {
            "key": "inflation",
            "title": "Inflation rate",
            "caption": f"{_long(latest)}, year on year",
            "value": float(inflation[latest]),
            "unit": "percent",
            "delta": _delta(
                float(inflation[latest] - inflation[previous]), "points", f"from {_long(previous)}",
                good_when_up=None,
            ),
        },
    ]

    recent = cash.iloc[-HISTORY_MONTHS_ON_FORECAST_CHART:]
    table = {"months": forecasts["months"], **forecasts["models"][best["key"]]}
    direction = trend.classify_trend(cash, cash.index[0], latest)
    seasonal = analysis["seasonality"]
    relationship = analysis["relationship"]
    recent_check = next(item for item in relationship["checks"] if item["key"] == "recent")
    recent_start = _long(pd.Period(recent_check["start"], freq="M"))
    linked = [
        item["label"] for item in relationship["indicators"] if item["granger_significant_lags"]
    ]
    linked_recently = [
        item["label"] for item in recent_check["indicators"] if item["granger_significant_lags"]
    ]
    if linked:
        relationship_text = "Past values of " + _join(linked) + " help predict remittances."
    elif linked_recently:
        relationship_text = (
            "Over the whole period neither indicator helps predict remittances, but from "
            f"{recent_start} {_join(linked_recently)} does."
        )
    else:
        relationship_text = (
            "Neither indicator's past values help predict remittances in the Granger tests, "
            f"over the whole period or from {recent_start}."
        )
    selection = metrics["selection"]
    # The runner-up, and whether the test can tell it apart from the main model.
    runner_up = sorted(
        (row for row in metrics["models"] if row["candidate"] and row["key"] != best["key"]),
        key=lambda row: row[selection["metric"]],
    )[0]
    tied = not runner_up["versus_best"]["different"]

    highlights = [
        {
            "title": "Trend",
            "text": f"The 12-month average is {direction['direction']}, about "
            f"{abs(direction['annual_change_pct']):.1f}% a year since "
            f"{_long(pd.Period(direction['from'], freq='M'))}.",
            "href": "/trends",
        },
        {
            "title": "Seasonality",
            "text": "Remittances are usually highest in "
            + _join(seasonal["highest_months"])
            + " and lowest in "
            + _join(seasonal["lowest_months"])
            + ".",
            "href": "/seasonality",
        },
        {
            "title": "Exchange rate and inflation",
            "text": relationship_text,
            "href": "/relationships",
        },
        {
            "title": "Main model",
            "text": f"{best['name']} has the {selection['description'][0].lower()}{selection['description'][1:]}: "
            f"US${best[selection['metric']]:.1f} million."
            + (
                f" The runner-up, {runner_up['name']}, cannot be told apart from it statistically."
                if tied
                else ""
            ),
            "href": "/models",
        },
    ]

    return {
        "latest_month": str(latest),
        "kpis": kpis,
        "highlights": highlights,
        "main_model": {"key": best["key"], "name": best["name"]},
        "chart": {
            "title": "Cash remittances and the 12-month forecast",
            "subtitle": f"US$ million per month; forecast by {best['name']}",
            "figure": figures.forecast_chart(
                recent.index, recent.tolist(), table, best["name"], interval_label=INTERVAL_LABEL
            ),
        },
    }


def _join(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C'"""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---- historical data ----

HISTORY_COLUMNS = {
    "cash": TARGET,
    "cash_yoy": TARGET_YOY,
    "fx": EXCHANGE_RATE,
    "fx_yoy": "php_per_usd_yoy_pct",
    "inflation": "inflation_yoy_pct",
}


def history(start: str | None, end: str | None) -> dict:
    (monthly,) = _require("monthly")
    begin, finish = _period_range(monthly, start, end)
    part = monthly.loc[begin:finish]
    months = part.index

    charts = [
        {
            "key": "cash",
            "title": "Cash remittances",
            "subtitle": "US$ million per month",
            "figure": figures.series_chart(months, part[TARGET].tolist(), "Cash remittances",
                                           y_title=figures.USD),
        },
        {
            "key": "fx",
            "title": "Peso per US dollar",
            "subtitle": "Monthly average, pesos",
            "figure": figures.series_chart(months, part[EXCHANGE_RATE].tolist(), "Peso per US dollar",
                                           y_title="Pesos per US$1", color=figures.SERIES[1],
                                           value_format=".2f"),
        },
        {
            "key": "fx_yoy",
            "title": "Peso per US dollar, change from a year earlier",
            "subtitle": "Percent; above zero means more pesos per dollar, a weaker peso",
            "figure": figures.series_chart(months, part["php_per_usd_yoy_pct"].tolist(),
                                           "Change from a year earlier", y_title="Percent",
                                           color=figures.SERIES[1], value_format="+.2f", suffix="%",
                                           zero_line=True),
        },
        {
            "key": "inflation",
            "title": "Inflation rate",
            "subtitle": "Year-on-year change of the consumer price index, percent",
            "figure": figures.series_chart(months, part["inflation_yoy_pct"].tolist(), "Inflation rate",
                                           y_title="Percent", color=figures.SERIES[2],
                                           value_format=".1f", suffix="%"),
        },
    ]
    rows = [
        {
            "month": str(month),
            **{name: float(row[column]) for name, column in HISTORY_COLUMNS.items()},
            "preliminary": bool(row["preliminary"]),
        }
        for month, row in part.iterrows()
    ]
    return {"range": _range_info(monthly, begin, finish), "charts": charts, "rows": rows}


def history_csv(start: str | None, end: str | None) -> tuple[str, str]:
    """The selected months as CSV text, and a file name for the download."""
    (monthly,) = _require("monthly")
    begin, finish = _period_range(monthly, start, end)
    part = monthly.loc[begin:finish].reset_index()
    part["month"] = part["month"].astype(str)
    buffer = io.StringIO()
    part.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue(), f"remittrend_{begin}_to_{finish}.csv"


# ---- trends ----

def trends(start: str | None, end: str | None) -> dict:
    (monthly,) = _require("monthly")
    begin, finish = _period_range(monthly, start, end)
    cash = monthly[TARGET]
    averages = trend.moving_averages(cash).loc[begin:finish]
    part = cash.loc[begin:finish]
    yoy = monthly[TARGET_YOY].loc[begin:finish]
    x = figures.dates(part.index)

    moving = figures.figure(
        [
            figures.line(x, part.tolist(), "Monthly", figures.NEUTRAL, width=1.5),
            figures.line(x, averages["ma_3"].tolist(), "3-month average", figures.SERIES[2]),
            figures.line(x, averages["ma_6"].tolist(), "6-month average", figures.SERIES[1]),
            figures.line(x, averages["ma_12"].tolist(), "12-month average", figures.SERIES[0], width=3),
        ],
        y_title=figures.USD,
    )
    change = figures.figure(
        [
            figures.bars(
                x,
                yoy.tolist(),
                "Change from a year earlier",
                [figures.SERIES[0] if value >= 0 else "token:chart-down" for value in yoy],
                value_format="+.2f",
                suffix="%",
            )
        ],
        y_title="Percent",
        showlegend=False,
        shapes=[figures.reference_line(0, dash="solid")],
    )

    annual = []
    for year, values in cash.groupby(cash.index.year):
        earlier = cash[(cash.index.year == year - 1) & cash.index.month.isin(values.index.month)]
        complete = len(values) == 12
        annual.append(
            {
                "year": int(year),
                "label": str(year) if complete else f"{year}, {_span(values.index[0], values.index[-1]).rsplit(' ', 1)[0]}",
                "complete": complete,
                "total": float(values.sum()),
                "average": float(values.mean()),
                # Against the same months of the year before, so part-years compare fairly.
                "change_pct": _pct(values.sum(), earlier.sum()) if len(earlier) == len(values) else None,
            }
        )

    return {
        "range": _range_info(monthly, begin, finish),
        "direction": trend.classify_trend(cash, begin, finish),
        "stable_band_pct": config.TREND_STABLE_BAND_PCT,
        "summary": trend.period_summary(cash, begin, finish),
        "charts": {
            "moving_averages": {
                "title": "Monthly remittances and moving averages",
                "subtitle": "US$ million; each average covers that month and the months before it",
                "figure": moving,
            },
            "change": {
                "title": "Change from the same month a year earlier",
                "subtitle": "Percent",
                "figure": change,
            },
        },
        "annual": annual,
    }


# ---- seasonality ----

def seasonality() -> dict:
    monthly, analysis = _require("monthly", "analysis")
    seasonal = analysis["seasonality"]
    profile = seasonal["profile"]
    parts = seasonal["decomposition"]
    by_year = seasonal["by_year"]
    months = parts["months"]
    years = seasonal["average_years"]
    # Years with no month that can be compared with its surroundings are left out.
    relative = [
        (year, row)
        for year, row in zip(by_year["years"], by_year["percent_of_trend"])
        if any(value is not None for value in row)
    ]

    def part_chart(key, title, subtitle, color, zero_line=False):
        return {
            "key": key,
            "title": title,
            "subtitle": subtitle,
            "figure": figures.series_chart(months, parts[key], title, y_title=figures.USD,
                                           color=color, zero_line=zero_line),
        }

    return {
        "strength": seasonal["strength"],
        "highest_months": seasonal["highest_months"],
        "lowest_months": seasonal["lowest_months"],
        "average_years": [years[0], years[-1]],
        "profile": profile,
        "charts": {
            "index": {
                "title": "Seasonal index by calendar month",
                "subtitle": "100 is an ordinary month; 110 means 10% above the level of the time",
                "figure": figures.month_bars(
                    [row["seasonal_index"] for row in profile], y_title="Seasonal index", baseline=100
                ),
            },
            "average": {
                "title": "Average remittance by calendar month",
                "subtitle": f"US$ million, average of {years[0]}–{years[-1]}",
                "figure": figures.month_bars(
                    [row["average"] for row in profile],
                    y_title=figures.USD,
                    baseline=sum(row["average"] for row in profile) / 12,
                    value_format=",.0f",
                ),
            },
            "heatmap_relative": {
                "title": "Each month against the level of its time",
                "subtitle": "Percent of the 12-month average centred on that month; "
                "blank where that average cannot be computed yet",
                "figure": figures.heatmap(
                    [year for year, _ in relative], [row for _, row in relative],
                    colorbar_title="Percent", diverging_around=100, value_format=".1f",
                ),
            },
            "heatmap_level": {
                "title": "Remittances by month and year",
                "subtitle": "US$ million",
                "figure": figures.heatmap(by_year["years"], by_year["values"], colorbar_title=figures.USD),
            },
        },
        "decomposition": [
            part_chart("trend", "Trend", "The level of remittances without the seasonal cycle", figures.SERIES[0]),
            part_chart("seasonal", "Seasonal", "The part that repeats every year", figures.SERIES[1], True),
            part_chart("residual", "Remainder", "What the trend and the season do not explain", figures.SERIES[2], True),
        ],
        "study_period": _span(monthly.index[0], monthly.index[-1]),
    }


# ---- relationships ----

FEATURE_LABELS = {
    "remittance_yoy_lag": "Remittance change, {n} months earlier",
    "remittance_yoy_mean": "Remittance change, average of the last {n} months",
    "php_per_usd_yoy_pct_lag": "Exchange rate change, {n} months earlier",
    "inflation_yoy_pct_lag": "Inflation, {n} months earlier",
}


def _feature_label(name: str) -> str:
    if name == "month":
        return "Calendar month"
    for prefix, label in FEATURE_LABELS.items():
        if name.startswith(prefix):
            n = int(name[len(prefix):])
            return label.format(n=n).replace("1 months", "1 month")
    return name


def _is_indicator_feature(name: str) -> bool:
    return name.startswith(("php_per_usd", "inflation"))


def relationships() -> dict:
    monthly, analysis, metrics = _require("monthly", "analysis", "metrics")
    related = analysis["relationship"]
    models = _model_rows(metrics)
    months = monthly.index
    observations = len(monthly) - 1
    threshold = 1.96 / observations**0.5

    series = [
        {
            "key": "cash_yoy",
            "title": "Cash remittances, change from a year earlier",
            "subtitle": "Percent",
            "figure": figures.series_chart(months, monthly[TARGET_YOY].tolist(), "Cash remittances",
                                           y_title="Percent", value_format="+.2f", suffix="%",
                                           zero_line=True),
        },
        {
            "key": "fx_yoy",
            "title": "Peso per US dollar, change from a year earlier",
            "subtitle": "Percent; above zero means a weaker peso",
            "figure": figures.series_chart(months, monthly["php_per_usd_yoy_pct"].tolist(),
                                           "Peso per US dollar", y_title="Percent",
                                           color=figures.SERIES[1], value_format="+.2f", suffix="%",
                                           zero_line=True),
        },
        {
            "key": "inflation",
            "title": "Inflation rate",
            "subtitle": "Percent, year on year",
            "figure": figures.series_chart(months, monthly["inflation_yoy_pct"].tolist(), "Inflation rate",
                                           y_title="Percent", color=figures.SERIES[2],
                                           value_format=".1f", suffix="%"),
        },
    ]

    indicators = []
    for item in related["indicators"]:
        significant_lags = [row["lag"] for row in item["correlations"] if row["significant"]]
        indicators.append(
            {
                "key": item["series"],
                "label": item["label"],
                "differenced": bool(item["differencing"]),
                "strongest_lag": item["strongest_lag"],
                "strongest_correlation": item["strongest_correlation"],
                "strongest_significant": item["strongest_significant"],
                "significant_lags": significant_lags,
                "granger": item["granger"],
                "granger_significant_lags": item["granger_significant_lags"],
                "figure": figures.lag_bars(item["correlations"], threshold),
            }
        )

    importance = []
    for key in ("rf_x", "xgb_x"):
        row = models[key]
        items = row["feature_importance"]
        labels = [_feature_label(item["feature"]) for item in items]
        values = [item["importance"] * 100 for item in items]
        colors = [
            figures.SERIES[1] if _is_indicator_feature(item["feature"]) else figures.SERIES[0]
            for item in items
        ]
        chart = figures.ranked_bars(labels, values, highlight=None, x_title="Share of importance, percent",
                                    value_format=".1f", suffix="%")
        chart["data"][0]["marker"]["color"] = colors
        importance.append(
            {
                "key": key,
                "model": row["name"],
                "indicator_share": sum(
                    item["importance"] for item in items if _is_indicator_feature(item["feature"])
                ) * 100,
                "figure": chart,
            }
        )

    coefficients = [
        {
            "model": models[key]["name"],
            "term": _feature_label(term["term"]),
            "coefficient": term["coefficient"],
            "p_value": term["p_value"],
            "significant": term["p_value"] < related["significance"],
        }
        for key in ("arimax", "sarimax")
        for term in models[key]["coefficients"]
    ]
    effect = [
        {
            "without": models[row["without"]]["name"],
            "with": models[row["with"]]["name"],
            "rmse_without": row["rmse_without"],
            "rmse_with": row["rmse_with"],
            "change_pct": _pct(row["rmse_with"], row["rmse_without"]),
            "improves": row["improves"],
            "rolling_without": row["rolling_without"],
            "rolling_with": row["rolling_with"],
            "rolling_change_pct": _pct(row["rolling_with"], row["rolling_without"]),
            "improves_rolling": row["improves_rolling"],
        }
        for row in metrics["indicator_effect"]
    ]

    # The same tests on the months after the pandemic swings, beside the whole period.
    def summary(item: dict) -> dict:
        return {
            "strongest_lag": item["strongest_lag"],
            "strongest_correlation": item["strongest_correlation"],
            "significant_lags": [row["lag"] for row in item["correlations"] if row["significant"]],
            "granger_significant_lags": item["granger_significant_lags"],
            "granger_lowest_p": min(row["p_value"] for row in item["granger"]),
        }

    checks = {item["key"]: item for item in related["checks"]}
    recent, undifferenced = checks["recent"], checks["undifferenced"]
    labels = {row["series"]: row["label"] for row in related["stationarity"]}
    variants = [
        {"key": "whole", "label": "Whole period", "indicators": related["indicators"]},
        {
            "key": "recent",
            "label": "From " + _long(pd.Period(recent["start"], freq="M")),
            "indicators": recent["indicators"],
        },
        {
            "key": "undifferenced",
            "label": "Whole period, indicator not differenced",
            "indicators": undifferenced["indicators"],
        },
    ]
    sensitivity = {
        "recent_period": _span(pd.Period(recent["start"], freq="M"), pd.Period(recent["end"], freq="M")),
        "recent_months": recent["months"],
        # Series on which ADF and KPSS disagree, so differencing is a judgement call.
        "disputed": [labels[series] for series in undifferenced["series"]],
        "rows": [
            {
                "label": whole["label"],
                "results": [
                    {"key": variant["key"], "label": variant["label"]}
                    | summary(variant["indicators"][position])
                    for variant in variants
                    # The undifferenced check only applies where the series was differenced
                    # and the tests disagree.
                    if variant["key"] != "undifferenced" or whole["series"] in undifferenced["series"]
                ],
            }
            for position, whole in enumerate(related["indicators"])
        ],
    }
    verdicts = {
        bool(result["granger_significant_lags"])
        for row in sensitivity["rows"]
        for result in row["results"]
    }
    sensitivity["same_conclusion"] = len(verdicts) == 1
    sensitivity["helps_predict"] = verdicts == {True}

    return {
        "study_period": _span(months[0], months[-1]),
        "significance": related["significance"],
        "target_label": related["target_label"],
        "series": series,
        "stationarity": related["stationarity"],
        "sensitivity": sensitivity,
        "rolling_windows": len(metrics["rolling_origins"]),
        "indicators": indicators,
        "overlap": related["indicator_overlap"],
        "importance": importance,
        "coefficients": coefficients,
        "indicator_lag": metrics["indicator_lag"],
        "effect": effect,
    }


# ---- model comparison ----

def models(selected: str | None) -> dict:
    (metrics,) = _require("metrics")
    rows = _model_rows(metrics)
    key = selected or metrics["best_model"]
    if key not in rows:
        raise BadRequest(f"Unknown model '{key}'.")
    chosen = rows[key]
    test = metrics["test"]
    split = metrics["split"]
    period = lambda a, b: _span(pd.Period(a, freq="M"), pd.Period(b, freq="M"))  # noqa: E731

    selection = metrics["selection"]
    ranked = sorted(metrics["models"], key=lambda row: row[selection["metric"]])
    table = [
        {
            name: row.get(name)
            for name in ("key", "name", "family", "candidate", "uses_indicators", "spec",
                         "training_rows", "mae", "rmse", "mape", "rolling_rmse", "coverage",
                         "interval_method")
        }
        | {
            "is_best": row["key"] == metrics["best_model"],
            # Diebold-Mariano test against the main model; None for the main model itself.
            "p_value": row["versus_best"]["p_value"] if row["versus_best"] else None,
            "different": row["versus_best"]["different"] if row["versus_best"] else None,
        }
        for row in ranked
    ]
    best = rows[metrics["best_model"]]
    by_window = selection["rule"] == "rolling"

    return {
        "best": {
            "key": best["key"],
            "name": best["name"],
            "rmse": best["rmse"],
            "mape": best["mape"],
            "rolling_rmse": best["rolling_rmse"],
        },
        "selection": {
            "rule": selection["rule"],
            "description": selection["description"],
            "windows": len(metrics["rolling_origins"]),
            "forecasts_compared": selection["forecasts_compared"],
            "best_on_test": rows[metrics["best_on_test"]]["name"],
            "best_on_rolling": rows[metrics["best_on_rolling"]]["name"],
            "agree": metrics["best_on_test"] == metrics["best_on_rolling"],
            "not_different": [
                row["name"] for row in ranked
                if row["candidate"] and row["versus_best"] and not row["versus_best"]["different"]
            ],
        },
        "interval_backtests": metrics["interval_backtests"],
        "selected": key,
        "split": {
            "train": period(split["train_start"], split["train_end"]),
            "test": period(split["test_start"], split["test_end"]),
            "train_months": len(pd.period_range(split["train_start"], split["train_end"], freq="M")),
            "test_months": len(test["months"]),
        },
        "models": table,
        "charts": {
            "rmse": {
                "title": (
                    f"RMSE averaged over the {len(metrics['rolling_origins'])} test windows"
                    if by_window
                    else "RMSE on the test months"
                ),
                "subtitle": "US$ million; lower is better",
                "figure": figures.ranked_bars(
                    [row["name"] for row in ranked], [row[selection["metric"]] for row in ranked],
                    highlight=best["name"], x_title="RMSE, US$ million",
                ),
            },
            "actual_vs_predicted": {
                "title": f"Actual against predicted: {chosen['name']}",
                "subtitle": f"US$ million, {period(split['test_start'], split['test_end'])}",
                "figure": figures.actual_vs_predicted(
                    test["months"], test["actual"], chosen["predicted"], chosen["name"],
                    chosen["lower"], chosen["upper"],
                ),
            },
        },
        "predictions": [
            {
                "month": month,
                "actual": actual,
                "predicted": predicted,
                "error": predicted - actual,
                "error_pct": _pct(predicted, actual),
            }
            for month, actual, predicted in zip(test["months"], test["actual"], chosen["predicted"])
        ],
        "rolling": {
            "origins": metrics["rolling_origins"],
            "rows": [
                {"key": row["key"], "name": row["name"], "rmse": [w["rmse"] for w in row["rolling"]],
                 "mean": row["rolling_rmse"]}
                for row in sorted(metrics["models"], key=lambda row: row["rolling_rmse"])
            ],
        },
        "with_actual_indicators": [
            {"name": row["name"], "rmse_held": row["rmse"], "rmse_actual": row["with_actual_indicators"]["rmse"]}
            for row in ranked
            if row.get("with_actual_indicators")
        ],
    }


def models_csv() -> tuple[str, str]:
    """The model comparison as CSV text, and a file name for the download."""
    (metrics,) = _require("metrics")
    selection = metrics["selection"]
    table = pd.DataFrame(
        [
            {
                "model": row["name"],
                "main_model": row["key"] == metrics["best_model"],
                "family": row["family"],
                "uses_indicators": row["uses_indicators"],
                "test_mae_usd_million": row["mae"],
                "test_rmse_usd_million": row["rmse"],
                "test_mape_pct": row["mape"],
                "rolling_rmse_usd_million": row["rolling_rmse"],
                "p_value_vs_main_model": row["versus_best"]["p_value"] if row["versus_best"] else None,
                "settings": row["spec"],
            }
            for row in sorted(metrics["models"], key=lambda row: row[selection["metric"]])
        ]
    )
    return _csv(table), f"remittrend_models_test_{metrics['split']['test_start']}_to_{metrics['split']['test_end']}.csv"


def _csv(table: pd.DataFrame) -> str:
    buffer = io.StringIO()
    table.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue()


# ---- forecast ----

def _number(text: str | None, name: str, low: float, high: float) -> float | None:
    if text is None or text == "":
        return None
    try:
        value = float(text)
    except ValueError as error:
        raise BadRequest(f"{name} must be a number.") from error
    if not (low <= value <= high):
        raise BadRequest(f"{name} must be between {low:g} and {high:g}.")
    return value


def forecast(model: str | None, horizon: str | None, exchange_rate: str | None, inflation: str | None) -> dict:
    monthly, forecasts, metrics = _require("monthly", "forecasts", "metrics")
    rows = _model_rows(metrics)
    key = model or metrics["best_model"]
    if key not in forecasts["models"]:
        raise BadRequest(f"Unknown model '{key}'.")
    try:
        months_ahead = int(horizon) if horizon else config.FORECAST_HORIZON
    except ValueError as error:
        raise BadRequest("The number of months must be a whole number.") from error
    if months_ahead not in HORIZONS:
        raise BadRequest(f"Choose {_join([str(h) for h in HORIZONS[:-1]])} or {HORIZONS[-1]} months.")
    rate = _number(exchange_rate, "The exchange rate", 30, 120)
    price_change = _number(inflation, "The inflation rate", -5, 30)

    chosen = rows[key]
    defaults = forecasts["assumptions"]
    saved = forecasts["models"][key]
    baseline = {"months": forecasts["months"][:months_ahead],
                **{name: saved[name][:months_ahead] for name in ("mean", "lower", "upper")}}
    custom = rate is not None or price_change is not None
    table = forecasting.forecast_table(_model(key), months_ahead, rate, price_change) if custom else baseline

    cash = monthly[TARGET]
    recent = cash.iloc[-HISTORY_MONTHS_ON_FORECAST_CHART:]
    result_rows = []
    for index, name in enumerate(table["months"]):
        month = pd.Period(name, freq="M")
        last_year = float(cash[month - 12]) if (month - 12) in cash.index else None
        mean = table["mean"][index]
        result_rows.append(
            {
                "month": name,
                "forecast": mean,
                "lower": table["lower"][index],
                "upper": table["upper"][index],
                "last_year": last_year,
                "change_pct": _pct(mean, last_year) if last_year else None,
                "difference": mean - baseline["mean"][index],
            }
        )

    total = sum(table["mean"])
    last_year_total = sum(row["last_year"] for row in result_rows if row["last_year"])
    first, last = (pd.Period(table["months"][i], freq="M") for i in (0, -1))
    # Every model's total for the same months, with the indicators held, so the
    # reader can see how far the models agree.
    metric = metrics["selection"]["metric"]
    comparison = sorted(
        (
            {
                "key": row["key"],
                "name": row["name"],
                "is_main": row["key"] == metrics["best_model"],
                "error": row[metric],
                "total": sum(forecasts["models"][row["key"]]["mean"][:months_ahead]),
            }
            for row in metrics["models"]
            if row["candidate"]
        ),
        key=lambda item: item["error"],
    )
    for item in comparison:
        item["change_pct"] = _pct(item["total"], last_year_total) if last_year_total else None

    # The indicator values this forecast was given, against the range the model was fitted on.
    indicator_range = None
    trained = (forecasts.get("trained_range") or {}).get(key)
    if trained:
        given = hold_indicators(monthly, months_ahead, rate, price_change)
        change = given["php_per_usd_yoy_pct"]
        price = float(given["inflation_yoy_pct"].iloc[0])
        indicator_range = {
            "exchange_rate_change": {
                "trained": trained["php_per_usd_yoy_pct"],
                "given": [float(change.min()), float(change.max())],
                "outside": bool(
                    change.min() < trained["php_per_usd_yoy_pct"][0]
                    or change.max() > trained["php_per_usd_yoy_pct"][1]
                ),
            },
            "inflation": {
                "trained": trained["inflation_yoy_pct"],
                "given": price,
                "outside": not (trained["inflation_yoy_pct"][0] <= price <= trained["inflation_yoy_pct"][1]),
            },
        }

    return {
        "comparison": comparison,
        "comparison_error": "rolling" if metric == "rolling_rmse" else "test",
        "model": {name: chosen[name] for name in ("key", "name", "family", "uses_indicators", "spec")}
        | {
            "has_intervals": table["lower"][0] is not None,
            "interval_method": chosen["interval_method"],
        },
        "interval_backtests": metrics["interval_backtests"],
        "horizon": months_ahead,
        "options": {
            "horizons": list(HORIZONS),
            "models": [
                {
                    "key": row["key"],
                    "name": row["name"],
                    "uses_indicators": row["uses_indicators"],
                    "is_main": row["key"] == metrics["best_model"],
                }
                for row in metrics["models"]
                if row["candidate"]
            ],
        },
        "last_observed": _long(monthly.index[-1]),
        "period": _span(first, last),
        "assumptions": {
            "exchange_rate": {"default": defaults[EXCHANGE_RATE], "used": rate if rate is not None else defaults[EXCHANGE_RATE]},
            "inflation": {"default": defaults["inflation_yoy_pct"], "used": price_change if price_change is not None else defaults["inflation_yoy_pct"]},
            "custom": custom,
            "indicator_lag": metrics["indicator_lag"],
            # Whether the entered values moved this model's forecast at all.
            "changed_forecast": any(abs(row["difference"]) > 1e-6 for row in result_rows),
            "range": indicator_range,
        },
        "total": {
            "forecast": total,
            "last_year": last_year_total,
            "change_pct": _pct(total, last_year_total) if last_year_total else None,
        },
        "chart": {
            "title": f"Forecast for {_span(first, last)}",
            "subtitle": f"US$ million per month, {chosen['name']}",
            "figure": figures.forecast_chart(
                recent.index, recent.tolist(), table, chosen["name"], interval_label=INTERVAL_LABEL
            ),
        },
        "rows": result_rows,
    }


def forecast_csv(model, horizon, exchange_rate, inflation) -> tuple[str, str]:
    """The forecast table as CSV text, and a file name for the download."""
    result = forecast(model, horizon, exchange_rate, inflation)
    table = pd.DataFrame(result["rows"]).rename(
        columns={
            "forecast": "forecast_usd_million",
            "lower": "lower_95_usd_million",
            "upper": "upper_95_usd_million",
            "last_year": "same_month_a_year_earlier_usd_million",
            "change_pct": "change_from_a_year_earlier_pct",
            "difference": "effect_of_assumptions_usd_million",
        }
    )
    table.insert(1, "model", result["model"]["name"])
    table["assumed_php_per_usd"] = result["assumptions"]["exchange_rate"]["used"]
    table["assumed_inflation_pct"] = result["assumptions"]["inflation"]["used"]
    first, last = result["rows"][0]["month"], result["rows"][-1]["month"]
    return _csv(table), f"remittrend_forecast_{result['model']['key']}_{first}_to_{last}.csv"


# ---- sources and countries ----

def sources(year: str | None) -> dict:
    by_source, by_country = _require("by_source", "by_country")
    years = sorted(int(y) for y in by_source.index.year.unique())
    counts = by_source.groupby(by_source.index.year).size()
    complete_years = [y for y in years if counts[y] == 12]
    try:
        chosen = int(year) if year else complete_years[-1]
    except ValueError as error:
        raise BadRequest("The year must be a number.") from error
    if chosen not in years:
        raise BadRequest(f"Choose a year from {years[0]} to {years[-1]}.")

    x = figures.dates(by_source.index)
    source_chart = figures.figure(
        [
            figures.line(x, by_source["land_based_usd_million"].tolist(), "Land-based", figures.SERIES[0]),
            figures.line(x, by_source["sea_based_usd_million"].tolist(), "Sea-based", figures.SERIES[1]),
        ],
        y_title=figures.USD,
    )
    yearly = []
    for y, part in by_source.groupby(by_source.index.year):
        total = part["cash_remittance_usd_million"].sum()
        yearly.append(
            {
                "year": int(y),
                "label": str(y) if len(part) == 12 else f"{y}, {_span(part.index[0], part.index[-1]).rsplit(' ', 1)[0]}",
                "land_based": float(part["land_based_usd_million"].sum()),
                "sea_based": float(part["sea_based_usd_million"].sum()),
                "total": float(total),
                "sea_share": float(part["sea_based_usd_million"].sum() / total * 100),
            }
        )

    in_year = by_country[by_country["month"].dt.year == chosen]
    months_in_year = sorted(in_year["month"].unique())
    earlier = by_country[
        (by_country["month"].dt.year == chosen - 1)
        & by_country["month"].dt.month.isin([m.month for m in months_in_year])
    ]
    totals = in_year.groupby("country")[
        ["cash_remittance_usd_million", "land_based_usd_million", "sea_based_usd_million"]
    ].sum().sort_values("cash_remittance_usd_million", ascending=False)
    earlier_totals = earlier.groupby("country")["cash_remittance_usd_million"].sum()
    grand_total = totals["cash_remittance_usd_million"].sum()

    countries = []
    for rank, (name, row) in enumerate(totals.head(TOP_COUNTRIES + 5).iterrows(), start=1):
        before = earlier_totals.get(name)
        countries.append(
            {
                "rank": rank,
                "country": name,
                "total": float(row["cash_remittance_usd_million"]),
                "share": float(row["cash_remittance_usd_million"] / grand_total * 100),
                "land_based": float(row["land_based_usd_million"]),
                "sea_based": float(row["sea_based_usd_million"]),
                "change_pct": _pct(row["cash_remittance_usd_million"], before) if before else None,
            }
        )
    top = countries[:TOP_COUNTRIES]

    # Growth of the five largest sources, complete years only, first year = 100.
    leaders = [row["country"] for row in countries[:5]]
    annual = (
        by_country[by_country["country"].isin(leaders) & by_country["month"].dt.year.isin(complete_years)]
        .groupby(["country", by_country["month"].dt.year])["cash_remittance_usd_million"]
        .sum()
        .unstack(0)
    )
    indexed = annual / annual.iloc[0] * 100
    growth_chart = figures.figure(
        [
            figures.line([str(y) for y in indexed.index], indexed[name].tolist(), name, figures.SERIES[i],
                         mode="lines+markers", marker={"size": 8, "color": figures.SERIES[i]})
            for i, name in enumerate(leaders)
        ],
        y_title=f"Index, {complete_years[0]} = 100",
        shapes=[figures.reference_line(100)],
        xaxis={"type": "category"},
    )

    period = _span(months_in_year[0], months_in_year[-1])
    return {
        "years": [{"year": y, "label": str(y) if counts[y] == 12 else f"{y} (to {by_source.index[-1].strftime('%B')})"} for y in years],
        "year": chosen,
        "period": period,
        "complete": len(months_in_year) == 12,
        "total": float(grand_total),
        "country_count": int((totals["cash_remittance_usd_million"] > 0).sum()),
        "yearly": yearly,
        "countries": countries,
        "charts": {
            "source": {
                "title": "Land-based and sea-based workers",
                "subtitle": "US$ million per month",
                "figure": source_chart,
            },
            "top": {
                "title": f"Ten largest sources, {period}",
                "subtitle": "US$ million",
                "figure": figures.ranked_bars(
                    [row["country"] for row in top], [row["total"] for row in top],
                    highlight=top[0]["country"], x_title=figures.USD, value_format=",.0f",
                ),
            },
            "growth": {
                "title": f"Growth of the five largest sources since {complete_years[0]}",
                "subtitle": f"Yearly total as an index, {complete_years[0]} = 100; complete years only",
                "figure": growth_chart,
            },
        },
    }
