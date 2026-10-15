"""Relationship of cash remittances with the exchange rate and inflation.

Stationarity tests, lagged correlations and Granger causality tests. These
describe statistical association and predictive value; they do not show that
one variable causes another.
"""

import warnings

import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, grangercausalitytests, kpss

from remittrend import config

SIGNIFICANCE = 0.05
MAX_CORRELATION_LAG = 12
MAX_GRANGER_LAG = 6

# Remittances are compared on a year-on-year basis: it removes the seasonal
# cycle and the long-run growth, and it is the basis of both indicators.
TARGET = "cash_remittance_yoy_pct"

SERIES_LABELS = {
    "cash_remittance_usd_million": "Cash remittances (US$ million)",
    "cash_remittance_yoy_pct": "Cash remittances, year-on-year change (%)",
    "php_per_usd_avg": "Peso per US dollar, monthly average",
    "php_per_usd_yoy_pct": "Peso per US dollar, year-on-year change (%)",
    "inflation_yoy_pct": "Inflation rate, year-on-year (%)",
}
INDICATORS = ("php_per_usd_avg", "php_per_usd_yoy_pct", "inflation_yoy_pct")


def adf_test(series: pd.Series) -> dict:
    """Augmented Dickey-Fuller test. A p-value below 0.05 means the series is stationary."""
    statistic, p_value, lags, observations, *_ = adfuller(
        series.dropna(), autolag="AIC", result_object=False
    )
    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "lags": int(lags),
        "observations": int(observations),
        "stationary": bool(p_value < SIGNIFICANCE),
    }


def kpss_test(series: pd.Series) -> dict:
    """KPSS test, which asks the opposite question to ADF.

    Here a p-value below 0.05 means the series is NOT stationary. statsmodels
    reports p-values only between 0.01 and 0.10; values at those ends mean
    "0.01 or less" and "0.10 or more".
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        statistic, p_value, lags, _ = kpss(series.dropna(), regression="c", nlags="auto")
    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "lags": int(lags),
        "stationary": bool(p_value >= SIGNIFICANCE),
    }


def stationarity(series: pd.Series) -> dict:
    """Both tests on one series, and what they say together."""
    adf, other = adf_test(series), kpss_test(series)
    if adf["stationary"] and other["stationary"]:
        verdict = "stationary"
    elif not adf["stationary"] and not other["stationary"]:
        verdict = "not stationary"
    else:
        # ADF cannot rule out a unit root but KPSS does not find one, or the reverse.
        verdict = "tests disagree"
    return {"adf": adf, "kpss": other, "verdict": verdict}


def stationarity_table(monthly: pd.DataFrame) -> list[dict]:
    """ADF and KPSS tests of each series as it is and after first differencing.

    The ADF test decides whether a series is differenced for the correlation
    and Granger tests, as the proposal states; KPSS is reported beside it as a
    second opinion.
    """
    rows = []
    for column, label in SERIES_LABELS.items():
        level = stationarity(monthly[column])
        differenced = stationarity(monthly[column].diff())
        rows.append(
            {
                "series": column,
                "label": label,
                "level": level,
                "first_difference": differenced,
                # Differencing order used in the correlation and Granger tests.
                "differencing": 0 if level["adf"]["stationary"] else 1,
            }
        )
    return rows


def make_stationary(monthly: pd.DataFrame, table: list[dict]) -> pd.DataFrame:
    """Each series, differenced once where the ADF test did not find it stationary."""
    order = {row["series"]: row["differencing"] for row in table}
    return pd.DataFrame(
        {column: monthly[column].diff() if order[column] else monthly[column] for column in order}
    )


def lagged_correlations(target: pd.Series, indicator: pd.Series, max_lag=MAX_CORRELATION_LAG) -> list[dict]:
    """Correlation of the target with the indicator k months earlier, for k = 0..max_lag."""
    rows = []
    for lag in range(max_lag + 1):
        pair = pd.concat([target, indicator.shift(lag)], axis=1).dropna()
        r, p_value = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
        rows.append(
            {
                "lag": lag,
                "correlation": float(r),
                "p_value": float(p_value),
                "observations": int(len(pair)),
                "significant": bool(p_value < SIGNIFICANCE),
            }
        )
    return rows


def granger_tests(target: pd.Series, indicator: pd.Series, max_lag=MAX_GRANGER_LAG) -> list[dict]:
    """Does the indicator's past help predict the target beyond the target's own past?

    One F-test per number of lags included (1..max_lag).
    """
    pair = pd.concat([target, indicator], axis=1).dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = grangercausalitytests(pair, maxlag=max_lag)
    rows = []
    for lag in range(1, max_lag + 1):
        f_statistic, p_value, *_ = results[lag][0]["ssr_ftest"]
        rows.append(
            {
                "lags": lag,
                "f_statistic": float(f_statistic),
                "p_value": float(p_value),
                "significant": bool(p_value < SIGNIFICANCE),
            }
        )
    return rows


def indicator_results(stationary: pd.DataFrame, order: dict) -> list[dict]:
    """Lagged correlations and Granger tests of each indicator against the target."""
    results = []
    for column in INDICATORS:
        correlations = lagged_correlations(stationary[TARGET], stationary[column])
        strongest = max(correlations, key=lambda row: abs(row["correlation"]))
        granger = granger_tests(stationary[TARGET], stationary[column])
        results.append(
            {
                "series": column,
                "label": SERIES_LABELS[column],
                "differencing": order[column],
                "correlations": correlations,
                "strongest_lag": strongest["lag"],
                "strongest_correlation": strongest["correlation"],
                "strongest_significant": strongest["significant"],
                "granger": granger,
                "granger_significant_lags": [row["lags"] for row in granger if row["significant"]],
            }
        )
    return results


def analyse(monthly: pd.DataFrame) -> dict:
    """Everything the relationship page shows, as plain lists and numbers."""
    table = stationarity_table(monthly)
    order = {row["series"]: row["differencing"] for row in table}
    stationary = make_stationary(monthly, table)

    # Check 1: the same tests on the months after the pandemic swings, with the
    # series transformed in the same way, so the results can be compared.
    recent = stationary.loc[config.RELATIONSHIP_RECENT_START :]

    # Check 2: where ADF and KPSS disagree about a series, differencing it is a
    # judgement call, so the tests are repeated with those series left as they are.
    disputed = [
        row["series"] for row in table
        if row["differencing"] == 1 and row["level"]["verdict"] == "tests disagree"
    ]
    relaxed_order = {series: 0 if series in disputed else d for series, d in order.items()}
    undifferenced = pd.DataFrame(
        {
            column: monthly[column].diff() if relaxed_order[column] else monthly[column]
            for column in relaxed_order
        }
    )

    def check(key: str, frame: pd.DataFrame, used_order: dict) -> dict:
        return {
            "key": key,
            "start": str(frame.index[0]),
            "end": str(frame.index[-1]),
            "months": int(len(frame)),
            "indicators": indicator_results(frame, used_order),
        }

    overlap = float(monthly["php_per_usd_yoy_pct"].corr(monthly["inflation_yoy_pct"]))
    return {
        "target": TARGET,
        "target_label": SERIES_LABELS[TARGET],
        "target_differencing": order[TARGET],
        "significance": SIGNIFICANCE,
        "study_period": [str(monthly.index[0]), str(monthly.index[-1])],
        "stationarity": table,
        "indicators": indicator_results(stationary, order),
        "checks": [
            check("recent", recent, order),
            check("undifferenced", undifferenced, relaxed_order) | {"series": disputed},
        ],
        # How much the two indicators move together; checked before both go in one model.
        "indicator_overlap": {
            "correlation": overlap,
            "variance_inflation_factor": float(1 / (1 - overlap**2)),
        },
    }
