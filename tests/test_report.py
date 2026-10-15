"""The paper exports and the manifest, built from what the pipeline has saved."""

import json

import pandas as pd
import pytest

from remittrend import config, report

OUTPUTS = {out.key: out.path for out in config.OUTPUTS}


@pytest.fixture(scope="module")
def data():
    if not all(path.is_file() for path in OUTPUTS.values()):
        pytest.skip("the pipeline has not been run")
    return report.load()


@pytest.fixture(scope="module")
def tables(data):
    return report.tables(data)


def test_tables_are_numbered_and_not_empty(tables):
    assert len(tables) == 13
    assert list(tables) == sorted(tables)
    for name, table in tables.items():
        assert len(table) > 0, name
        assert not table.columns.duplicated().any(), name


def test_model_table_matches_the_saved_comparison(tables, data):
    metrics = data["metrics"]
    table = tables["07_model_comparison"]
    assert len(table) == len(metrics["models"])
    main = table[table["main_model"]]
    assert len(main) == 1
    best = next(row for row in metrics["models"] if row["key"] == metrics["best_model"])
    assert main["model"].item() == best["name"]
    assert main["rolling_rmse"].item() == pytest.approx(best["rolling_rmse"])
    # The table is in the order of the selection rule, so the main model comes first.
    assert table["main_model"].iloc[0]
    assert pd.isna(main["dm_p_value_vs_main"].item())


def test_forecast_table_leads_with_the_main_model_and_its_interval(tables, data):
    forecasts, metrics = data["forecasts"], data["metrics"]
    table = tables["11_forecast"]
    assert list(table["month"]) == forecasts["months"]
    assert "(main model)" in table.columns[1]
    assert list(table.iloc[:, 1]) == pytest.approx(forecasts["models"][metrics["best_model"]]["mean"])
    assert (table["main_model_lower_95"] < table.iloc[:, 1]).all()
    assert len(table.columns) == 1 + 3 + 7  # month, main with interval, seven other models


def test_relationship_tables_cover_the_whole_period_and_both_checks(tables):
    assert tables["05_lagged_correlations"]["sample"].nunique() == 3
    assert tables["06_granger_tests"]["sample"].nunique() == 3
    stationarity = tables["04_stationarity_tests"]
    assert set(stationarity["form"]) == {"as it is", "first difference"}
    # Exactly one form of each series is the one used in the tests.
    assert (stationarity.groupby("series")["used_in_relationship_tests"].sum() == 1).all()


def test_export_writes_every_table_and_figure(tmp_path, tables):
    table_paths, figure_paths = report.export(tmp_path)
    assert [path.stem for path in table_paths] == list(tables)
    assert len(figure_paths) == 8
    for path in [*table_paths, *figure_paths]:
        assert path.stat().st_size > 0
    assert all(path.suffix == ".png" for path in figure_paths)
    written = pd.read_csv(tmp_path / "tables" / "07_model_comparison.csv")
    assert list(written["model"]) == list(tables["07_model_comparison"]["model"])


def test_manifest_records_data_settings_and_software(tmp_path, data):
    path = tmp_path / "manifest.json"
    manifest = report.write_manifest(path)
    assert json.loads(path.read_text()) == json.loads(json.dumps(manifest))

    monthly = data["monthly"]
    assert manifest["study_period"]["start"] == str(monthly.index[0])
    assert manifest["study_period"]["end"] == str(monthly.index[-1])
    assert manifest["study_period"]["months"] == len(monthly)
    assert manifest["main_model"]["key"] == data["metrics"]["best_model"]
    assert manifest["settings"]["MODEL_SELECTION"] == config.MODEL_SELECTION
    assert manifest["software"]["pandas"] == pd.__version__

    found = [item for item in config.RAW_INPUTS if item.find() is not None]
    assert len(manifest["raw_files"]) == len(found)
    for record in manifest["raw_files"]:
        assert len(record["sha256"]) == 64
        assert record["bytes"] > 0
    assert {record["file"] for record in manifest["outputs"]} == {
        out.relative_path for out in config.OUTPUTS
    }
