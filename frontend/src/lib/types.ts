import type { Figure } from "@/components/chart"

/** A chart with its heading, as the API sends it. */
export type ChartBlock = {
  key?: string
  title: string
  subtitle: string
  figure: Figure
}

export type Delta = {
  value: number
  unit: "percent" | "usd_million" | "points"
  direction: "up" | "down" | "flat"
  tone: "good" | "bad" | "neutral"
  text: string
}

export type Kpi = {
  key: string
  title: string
  caption: string
  value: number
  unit: "usd_million" | "percent_change" | "percent" | "peso"
  delta: Delta
  /** The 95% prediction interval of a forecast figure. */
  range?: { lower: number; upper: number } | null
}

export type MonthRange = {
  min: string
  max: string
  start: string
  end: string
  label: string
}

export type Overview = {
  latest_month: string
  kpis: Kpi[]
  highlights: { title: string; text: string; href: string }[]
  main_model: { key: string; name: string }
  chart: ChartBlock
}

export type HistoryRow = {
  month: string
  cash: number
  cash_yoy: number
  fx: number
  fx_yoy: number
  inflation: number
  preliminary: boolean
}

export type History = {
  range: MonthRange
  charts: ChartBlock[]
  rows: HistoryRow[]
}

export type Trends = {
  range: MonthRange
  direction: {
    direction: "rising" | "falling" | "stable" | null
    annual_change_pct: number | null
    from: string | null
    to: string | null
  }
  stable_band_pct: number
  summary: {
    months: number
    total: number
    average: number
    first: number
    last: number
    change_pct: number
    highest_month: string
    lowest_month: string
  }
  charts: { moving_averages: ChartBlock; change: ChartBlock }
  annual: {
    year: number
    label: string
    complete: boolean
    total: number
    average: number
    change_pct: number | null
  }[]
}

export type Seasonality = {
  strength: number
  highest_months: string[]
  lowest_months: string[]
  average_years: [number, number]
  profile: { month: number; label: string; average: number; seasonal_index: number; rank: number }[]
  charts: {
    index: ChartBlock
    average: ChartBlock
    heatmap_relative: ChartBlock
    heatmap_level: ChartBlock
  }
  decomposition: ChartBlock[]
  study_period: string
}

export type TestResult = { statistic: number; p_value: number; lags: number; stationary: boolean }

/** ADF and KPSS on one series, and what they say together. */
export type Stationarity = {
  adf: TestResult
  kpss: TestResult
  verdict: "stationary" | "not stationary" | "tests disagree"
}

/** The relationship tests for one indicator on one sample. */
export type RelationshipSummary = {
  strongest_lag: number
  strongest_correlation: number
  significant_lags: number[]
  granger_significant_lags: number[]
  granger_lowest_p: number
}

export type Relationships = {
  study_period: string
  significance: number
  target_label: string
  series: ChartBlock[]
  stationarity: {
    series: string
    label: string
    level: Stationarity
    first_difference: Stationarity
    differencing: number
  }[]
  sensitivity: {
    recent_period: string
    recent_months: number
    /** Series on which the two stationarity tests disagree. */
    disputed: string[]
    rows: {
      label: string
      results: ({ key: string; label: string } & RelationshipSummary)[]
    }[]
    same_conclusion: boolean
    helps_predict: boolean
  }
  rolling_windows: number
  indicators: {
    key: string
    label: string
    differenced: boolean
    strongest_lag: number
    strongest_correlation: number
    strongest_significant: boolean
    significant_lags: number[]
    granger: { lags: number; f_statistic: number; p_value: number; significant: boolean }[]
    granger_significant_lags: number[]
    figure: Figure
  }[]
  overlap: { correlation: number; variance_inflation_factor: number }
  importance: { key: string; model: string; indicator_share: number; figure: Figure }[]
  coefficients: {
    model: string
    term: string
    coefficient: number
    p_value: number
    significant: boolean
  }[]
  indicator_lag: number
  effect: {
    without: string
    with: string
    rmse_without: number
    rmse_with: number
    change_pct: number
    improves: boolean
    rolling_without: number
    rolling_with: number
    rolling_change_pct: number
    improves_rolling: boolean
  }[]
}

export type ModelRow = {
  key: string
  name: string
  family: "statistical" | "machine learning" | "reference"
  candidate: boolean
  uses_indicators: boolean
  spec: string
  training_rows: number
  mae: number
  rmse: number
  mape: number
  rolling_rmse: number
  is_best: boolean
  /** How many test months fell inside the model's 95% interval. */
  coverage: { inside: number; months: number } | null
  interval_method: "model" | "backtest" | null
  /** Diebold-Mariano test against the main model; null for the main model. */
  p_value: number | null
  different: boolean | null
}

export type Models = {
  best: { key: string; name: string; rmse: number; mape: number; rolling_rmse: number }
  selection: {
    rule: "rolling" | "test"
    description: string
    windows: number
    forecasts_compared: number
    best_on_test: string
    best_on_rolling: string
    agree: boolean
    not_different: string[]
  }
  interval_backtests: number
  selected: string
  split: { train: string; test: string; train_months: number; test_months: number }
  models: ModelRow[]
  charts: { rmse: ChartBlock; actual_vs_predicted: ChartBlock }
  predictions: {
    month: string
    actual: number
    predicted: number
    error: number
    error_pct: number
  }[]
  rolling: {
    origins: string[]
    rows: { key: string; name: string; rmse: number[]; mean: number }[]
  }
  with_actual_indicators: { name: string; rmse_held: number; rmse_actual: number }[]
}

export type Forecast = {
  model: {
    key: string
    name: string
    family: string
    uses_indicators: boolean
    has_intervals: boolean
    interval_method: "model" | "backtest" | null
    spec: string
  }
  interval_backtests: number
  horizon: number
  options: {
    horizons: number[]
    models: { key: string; name: string; uses_indicators: boolean; is_main: boolean }[]
  }
  last_observed: string
  period: string
  assumptions: {
    exchange_rate: { default: number; used: number }
    inflation: { default: number; used: number }
    custom: boolean
    indicator_lag: number
    changed_forecast: boolean
    /** The indicator values given to the model against the range it was fitted on. */
    range: {
      exchange_rate_change: { trained: [number, number]; given: [number, number]; outside: boolean }
      inflation: { trained: [number, number]; given: number; outside: boolean }
    } | null
  }
  total: { forecast: number; last_year: number; change_pct: number | null }
  comparison: {
    key: string
    name: string
    is_main: boolean
    error: number
    total: number
    change_pct: number | null
  }[]
  comparison_error: "rolling" | "test"
  chart: ChartBlock
  rows: {
    month: string
    forecast: number
    lower: number | null
    upper: number | null
    last_year: number | null
    change_pct: number | null
    difference: number
  }[]
}

export type Sources = {
  years: { year: number; label: string }[]
  year: number
  period: string
  complete: boolean
  total: number
  country_count: number
  yearly: {
    year: number
    label: string
    land_based: number
    sea_based: number
    total: number
    sea_share: number
  }[]
  countries: {
    rank: number
    country: string
    total: number
    share: number
    land_based: number
    sea_based: number
    change_pct: number | null
  }[]
  charts: { source: ChartBlock; top: ChartBlock; growth: ChartBlock }
}
