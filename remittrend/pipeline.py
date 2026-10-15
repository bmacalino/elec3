"""Command-line entry point.

    python -m remittrend.pipeline check     # are the raw files in place?
    python -m remittrend.pipeline ingest    # raw files -> data/processed
    python -m remittrend.pipeline analyze   # seasonal and relationship analysis
    python -m remittrend.pipeline train     # compare the models and forecast
    python -m remittrend.pipeline report    # tables and figures for the paper, and the manifest
    python -m remittrend.pipeline all       # run every stage in order
"""

import argparse
import sys

from remittrend import (
    artifacts,
    config,
    dataset,
    forecast,
    ingest,
    relationship,
    report,
    seasonality,
)

OUTPUTS = {out.key: out.path for out in config.OUTPUTS}


def check() -> bool:
    """Report which raw files are present in data/raw."""
    print(f"Raw files in {config.RAW_DIR}:")
    all_found = True
    for raw in config.RAW_INPUTS:
        found = raw.find()
        all_found = all_found and found is not None
        state = found.name if found else f"MISSING (expected {raw.patterns[0]})"
        print(f"  {raw.label} [{raw.source}]: {state}")
    return all_found


def run_ingest() -> bool:
    """Parse the raw files and write the tables in data/processed."""
    raw = {item.key: item.find() for item in config.RAW_INPUTS}

    remittances = ingest.read_remittances(raw["ofwp"])
    exchange_rate = ingest.read_exchange_rate(raw["exchange_rate"])
    cpi_yoy = ingest.read_cpi_yoy(raw["cpi"])
    months = dataset.study_months(remittances, exchange_rate, cpi_yoy)
    areas = ingest.read_remittances_by_area(raw["ofw"], months[0].year, months[-1].year)

    monthly = dataset.build_monthly(remittances, exchange_rate, cpi_yoy, months)
    by_source = dataset.build_by_source(areas, months)
    by_country = dataset.build_by_country(areas, months)

    dataset.write_csv(monthly, OUTPUTS["monthly"])
    dataset.write_csv(by_source, OUTPUTS["by_source"])
    dataset.write_csv(by_country, OUTPUTS["by_country"])

    frozen = " (frozen by STUDY_END in config.py)" if config.STUDY_END else ""
    print(f"Study period {months[0]} to {months[-1]}: {len(monthly)} months{frozen}")
    print(f"  monthly.csv     {len(monthly)} rows")
    print(f"  by_source.csv   {len(by_source)} rows")
    print(f"  by_country.csv  {len(by_country)} rows, {by_country['country'].nunique()} countries")
    return True


def run_analyze() -> bool:
    """Seasonal and relationship analysis of the monthly dataset -> artifacts/analysis.json."""
    monthly = dataset.read_monthly()

    seasonal = seasonality.analyse(monthly["cash_remittance_usd_million"])
    related = relationship.analyse(monthly)
    artifacts.write_json(OUTPUTS["analysis"], {"seasonality": seasonal, "relationship": related})

    print(f"Seasonality: strength {seasonal['strength']:.2f}; "
          f"highest months {', '.join(seasonal['highest_months'])}; "
          f"lowest months {', '.join(seasonal['lowest_months'])}")
    labels = {"recent": "from {start}", "undifferenced": "indicators not differenced where the tests disagree"}
    samples = [("whole period", related["indicators"])] + [
        (labels[item["key"]].format(**item), item["indicators"]) for item in related["checks"]
    ]
    for label, results in samples:
        print(f"Relationship with remittances, {label}:")
        for item in results:
            granger = item["granger_significant_lags"]
            print(
                f"  {item['label']}: strongest correlation "
                f"{item['strongest_correlation']:+.2f} at lag {item['strongest_lag']}; "
                f"Granger significant at lags {granger if granger else 'none'}"
            )
    return True


def run_train() -> bool:
    """Choose, compare and refit the models -> metrics.json, forecasts.json, models/."""
    monthly = dataset.read_monthly()

    print("Comparing the models (about five minutes: settings are chosen again for every test window)...")
    comparison, models = forecast.compare(monthly, progress=print)
    artifacts.write_json(OUTPUTS["metrics"], comparison)

    print("  refitting on every month and forecasting ahead")
    fitted = forecast.fit_all(monthly, models)
    forecast.save_models(fitted)
    artifacts.write_json(OUTPUTS["forecasts"], forecast.default_forecasts(fitted))

    split = comparison["split"]
    best = comparison["best_model"]
    print(f"Test period {split['test_start']} to {split['test_end']} (US$ million):")
    print(f"  {'Model':<32}{'MAE':>9}{'RMSE':>9}{'MAPE %':>9}{'Rolling RMSE':>14}{'p vs main':>11}")
    for row in sorted(comparison["models"], key=lambda r: r[comparison["selection"]["metric"]]):
        versus = row["versus_best"]
        p_value = "" if versus is None or versus["p_value"] is None else f"{versus['p_value']:.3f}"
        mark = " *" if row["key"] == best else ""
        print(
            f"  {row['name']:<32}{row['mae']:>9.1f}{row['rmse']:>9.1f}"
            f"{row['mape']:>9.2f}{row['rolling_rmse']:>14.1f}{p_value:>11}{mark}"
        )
    print(f"  * main model. Rule: {comparison['selection']['description']}.")
    return True


def run_report() -> bool:
    """Tables and figures for the paper, and a record of how the results were produced."""
    tables, figures = report.export()
    manifest = report.write_manifest()
    print(f"Paper outputs in {config.PAPER_DIR}: {len(tables)} tables, {len(figures)} figures")
    print(f"Manifest: {config.MANIFEST_PATH} (study period {manifest['study_period']['start']} "
          f"to {manifest['study_period']['end']}, main model {manifest['main_model']['name']})")
    return True


# Stages run in this order.
STAGES = {
    "check": check,
    "ingest": run_ingest,
    "analyze": run_analyze,
    "train": run_train,
    "report": run_report,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m remittrend.pipeline")
    parser.add_argument("stage", choices=[*STAGES, "all"])
    args = parser.parse_args(argv)

    names = list(STAGES) if args.stage == "all" else [args.stage]
    for name in names:
        if not STAGES[name]():
            print(f"Stopped at '{name}'.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
