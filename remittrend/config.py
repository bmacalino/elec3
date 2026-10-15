"""Paths and study settings shared by the pipeline and the web app."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
# The group's own hand-cleaned files, used only to cross-check the parsers.
REFERENCE_DIR = ROOT / "data" / "reference"
PROCESSED_DIR = ROOT / "data" / "processed"
ARTIFACTS_DIR = ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
MANIFEST_PATH = ARTIFACTS_DIR / "manifest.json"
# Tables and figures exported for the paper.
PAPER_DIR = ROOT / "paper"

# The study period starts when the 2018-based inflation series starts.
STUDY_START = "2019-01"
# None: the period ends at the latest month that all three series cover, so a
# new month is picked up when the raw files are replaced. Set a month, for
# example "2026-06", to freeze the period and keep a paper's results fixed.
STUDY_END = None
# The most recent months are held out to compare the models.
TEST_MONTHS = 12
SEASONAL_PERIOD = 12
RANDOM_SEED = 42
# Months forecast ahead, in the model comparison and on the dashboard.
FORECAST_HORIZON = 12
# The exchange rate and inflation enter the models with at least this lag, so
# the first months of a forecast rely on values already observed.
INDICATOR_LAG = 3
# The 12-month comparison is repeated on earlier windows, each starting this
# many months before the next. The last window is the testing period.
ROLLING_WINDOWS = 5
ROLLING_STEP = 6
# How the main model is chosen among the candidates:
#   "rolling"  lowest RMSE averaged over all the windows above
#   "test"     lowest RMSE on the testing period alone
MODEL_SELECTION = "rolling"
# Prediction intervals of the tree models come from the errors of this many
# earlier forecasts, one started in each of the preceding months.
INTERVAL_BACKTEST_ORIGINS = 36
# The relationship tests are repeated from this month on, to see whether the
# 2020-2021 pandemic swings drive the result.
RELATIONSHIP_RECENT_START = "2022-01"
# A change in the 12-month moving average within this many percent per year,
# up or down, is reported as "stable".
TREND_STABLE_BAND_PCT = 1.0


@dataclass(frozen=True)
class RawInput:
    key: str
    label: str
    source: str
    # File name patterns accepted in data/raw, tried in order.
    patterns: tuple[str, ...]

    def find(self, raw_dir: Path = RAW_DIR) -> Path | None:
        for pattern in self.patterns:
            matches = sorted(p for p in raw_dir.glob(pattern) if p.is_file())
            if matches:
                return matches[0]
        return None


RAW_INPUTS = (
    RawInput(
        key="ofwp",
        label="Monthly personal and cash remittances",
        source="BSP",
        patterns=("Original_ofwp.xlsx", "ofwp.xlsx", "ofwp.xls"),
    ),
    RawInput(
        key="ofw",
        label="Cash remittances by country and source",
        source="BSP",
        patterns=("Original_ofw.xlsx", "ofw.xlsx", "ofw.xls"),
    ),
    RawInput(
        key="exchange_rate",
        label="Peso per US dollar exchange rate (daily, monthly, annual)",
        source="BSP",
        patterns=(
            "Original_ExchangeRate_whole.xlsx",
            "pesodollar.xlsx",
            "pesodollar.xls",
            "*[Ee]xchange*.xls*",
            "*dollar*.xls*",
        ),
    ),
    RawInput(
        key="cpi",
        label="Year-on-year change of the CPI, all items, Philippines (2018=100)",
        source="PSA OpenSTAT",
        patterns=(
            "Original_PSA_PriceIndices.csv",
            "cpi_yoy.csv",
            "0012M4ACP23*.csv",
            "*[Pp]rice[Ii]ndices*.csv",
            "*cpi*.csv",
        ),
    ),
)


@dataclass(frozen=True)
class Output:
    key: str
    path: Path

    @property
    def relative_path(self) -> str:
        if self.path.is_relative_to(ROOT):
            return self.path.relative_to(ROOT).as_posix()
        return self.path.as_posix()


# Files the pipeline writes and the web app reads.
OUTPUTS = (
    Output("monthly", PROCESSED_DIR / "monthly.csv"),
    Output("by_source", PROCESSED_DIR / "by_source.csv"),
    Output("by_country", PROCESSED_DIR / "by_country.csv"),
    Output("analysis", ARTIFACTS_DIR / "analysis.json"),
    Output("metrics", ARTIFACTS_DIR / "metrics.json"),
    Output("forecasts", ARTIFACTS_DIR / "forecasts.json"),
)
