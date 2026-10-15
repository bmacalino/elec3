"""What every forecasting model has in common.

A model is fitted on the monthly dataset up to some month (the history) and
forecasts the months after it. Models that use the exchange rate and inflation
also need those indicators for the forecast months; `hold_indicators` supplies
them from an assumption, since their future values are unknown.
"""

import pandas as pd

TARGET = "cash_remittance_usd_million"
TARGET_YOY = "cash_remittance_yoy_pct"
EXCHANGE_RATE = "php_per_usd_avg"
# The indicators used as model inputs. The exchange rate enters as its
# year-on-year change, the same basis as inflation.
INDICATORS = ("php_per_usd_yoy_pct", "inflation_yoy_pct")
INDICATOR_COLUMNS = (EXCHANGE_RATE, *INDICATORS)

INTERVAL_LEVEL = 0.95


class Forecaster:
    """Base class. Subclasses set the attributes below and implement fit and forecast."""

    key: str
    name: str
    family: str  # "statistical", "machine learning" or "reference"
    uses_indicators: bool = False
    has_intervals: bool = False
    # Where the prediction interval comes from: "model" or "backtest"; None if there is none.
    interval_method: str | None = None
    spec: str = ""

    def fit(self, history: pd.DataFrame) -> "Forecaster":
        raise NotImplementedError

    def forecast(self, horizon: int, future_indicators: pd.DataFrame | None = None) -> pd.DataFrame:
        """Columns mean, lower, upper (NaN where the model has no interval), one row per month."""
        raise NotImplementedError

    def details(self) -> dict:
        """Model-specific results for the comparison page: coefficients, feature importance."""
        return {}


def future_months(history: pd.DataFrame, horizon: int) -> pd.PeriodIndex:
    return pd.period_range(history.index[-1] + 1, periods=horizon, freq="M")


def hold_indicators(
    history: pd.DataFrame,
    horizon: int,
    exchange_rate: float | None = None,
    inflation: float | None = None,
) -> pd.DataFrame:
    """Indicators for the forecast months under a flat assumption.

    Each assumed value applies to every forecast month; left as None, the last
    observed value is carried forward. The year-on-year change of the exchange
    rate follows from the assumed rate and the rate observed a year earlier.
    """
    months = future_months(history, horizon)
    rate = history[EXCHANGE_RATE].iloc[-1] if exchange_rate is None else exchange_rate
    inflation = history["inflation_yoy_pct"].iloc[-1] if inflation is None else inflation

    rates = pd.concat([history[EXCHANGE_RATE], pd.Series(float(rate), index=months)])
    change = (rates / rates.shift(12) - 1) * 100
    return pd.DataFrame(
        {
            EXCHANGE_RATE: float(rate),
            "php_per_usd_yoy_pct": change.loc[months],
            "inflation_yoy_pct": float(inflation),
        },
        index=months,
    )


def with_future(history: pd.DataFrame, future_indicators: pd.DataFrame) -> pd.DataFrame:
    """The history followed by the forecast months, which carry indicators only."""
    future = future_indicators.reindex(columns=history.columns)
    return pd.concat([history, future])


class SeasonalNaive(Forecaster):
    """Reference only: each month repeats the same month a year earlier."""

    key = "seasonal_naive"
    name = "Same month last year"
    family = "reference"
    spec = "Seasonal naive"

    def fit(self, history):
        self.history = history
        return self

    def forecast(self, horizon, future_indicators=None):
        values = list(self.history[TARGET])
        for _ in range(horizon):
            values.append(values[-12])
        return pd.DataFrame(
            {"mean": values[-horizon:], "lower": float("nan"), "upper": float("nan")},
            index=future_months(self.history, horizon),
        )
