import json

import pytest

from app import create_app
from remittrend import config, dataset
from remittrend.models.base import TARGET

OUTPUTS = {out.key: out.path for out in config.OUTPUTS}


@pytest.fixture
def client(tmp_path):
    # Point at an empty folder so the tests do not depend on a frontend build.
    return create_app(frontend_dist=tmp_path).test_client()


@pytest.fixture
def ready():
    """Skip tests of the data routes until the pipeline has produced its files."""
    missing = [key for key, path in OUTPUTS.items() if not path.is_file()]
    if missing or not (config.MODELS_DIR / "sarimax.joblib").is_file():
        pytest.skip("the pipeline has not been run")


@pytest.fixture(scope="module")
def saved_monthly():
    if not OUTPUTS["monthly"].is_file():
        pytest.skip("the pipeline has not been run")
    return dataset.read_csv(OUTPUTS["monthly"]).set_index("month")


def no_nan(payload) -> bool:
    """JSON from the API must not contain NaN, which browsers cannot parse."""
    return "NaN" not in json.dumps(payload) and "Infinity" not in json.dumps(payload)


# ---- always available ----

def test_status_lists_every_raw_input_and_output(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.get_json()
    assert [r["key"] for r in body["raw"]] == [r.key for r in config.RAW_INPUTS]
    assert [o["key"] for o in body["outputs"]] == [o.key for o in config.OUTPUTS]
    for output in body["outputs"]:
        assert isinstance(output["exists"], bool)


def test_unknown_api_route_is_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.is_json


def test_missing_asset_is_404_not_the_page(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>RemitTrend PH</title>")
    client = create_app(frontend_dist=tmp_path).test_client()
    assert client.get("/assets/missing.js").status_code == 404


def test_frontend_not_built_is_503(client):
    assert client.get("/").status_code == 503


def test_page_routes_fall_back_to_index(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>RemitTrend PH</title>")
    client = create_app(frontend_dist=tmp_path).test_client()
    for path in ("/", "/history", "/forecast"):
        response = client.get(path)
        assert response.status_code == 200
        assert b"RemitTrend PH" in response.data


def test_data_route_reports_what_is_missing(client, monkeypatch, tmp_path):
    from app import services

    absent = {key: config.Output(key, tmp_path / f"{key}.csv") for key in services.OUTPUTS}
    monkeypatch.setattr(services, "OUTPUTS", absent)
    response = client.get("/api/history")
    assert response.status_code == 503
    assert response.get_json()["error"] == "not_ready"


# ---- pages ----

@pytest.fixture
def saved_vintage(saved_monthly):
    """For checks against the proposal's figures, which are for the files ending June 2026."""
    if str(saved_monthly.index[-1]) != "2026-06":
        pytest.skip("the dataset has moved past the months the proposal quotes")


@pytest.fixture
def metrics(ready):
    return json.loads(OUTPUTS["metrics"].read_text())


@pytest.mark.parametrize(
    "path",
    ["/api/overview", "/api/history", "/api/trends", "/api/seasonality", "/api/relationships",
     "/api/models", "/api/forecast", "/api/sources"],
)
def test_every_page_route_answers_with_clean_json(client, ready, path):
    response = client.get(path)
    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    assert no_nan(response.get_json())


def test_overview_cards_match_the_dataset(client, ready, saved_monthly):
    body = client.get("/api/overview").get_json()
    cards = {card["key"]: card for card in body["kpis"]}
    assert list(cards) == ["latest", "mom", "yoy", "ytd", "next", "exchange_rate", "inflation"]

    cash = saved_monthly[TARGET]
    latest = cash.index[-1]
    assert body["latest_month"] == str(latest)
    assert cards["latest"]["value"] == pytest.approx(cash.iloc[-1])
    assert cards["mom"]["value"] == pytest.approx((cash.iloc[-1] / cash.iloc[-2] - 1) * 100)
    assert cards["yoy"]["value"] == pytest.approx((cash.iloc[-1] / cash.iloc[-13] - 1) * 100)
    assert cards["ytd"]["value"] == pytest.approx(cash[cash.index.year == latest.year].sum())
    assert cards["exchange_rate"]["value"] == pytest.approx(saved_monthly["php_per_usd_avg"].iloc[-1])
    assert cards["inflation"]["value"] == pytest.approx(saved_monthly["inflation_yoy_pct"].iloc[-1])
    for card in cards.values():
        assert card["delta"]["direction"] in {"up", "down", "flat"}
    # Up is not "good" for the exchange rate or inflation.
    assert cards["exchange_rate"]["delta"]["tone"] == "neutral"
    assert cards["inflation"]["delta"]["tone"] == "neutral"


def test_overview_forecast_card_uses_the_main_model(client, metrics):
    body = client.get("/api/overview").get_json()
    forecasts = json.loads(OUTPUTS["forecasts"].read_text())
    table = forecasts["models"][metrics["best_model"]]
    card = next(card for card in body["kpis"] if card["key"] == "next")
    assert body["main_model"]["key"] == metrics["best_model"]
    assert card["value"] == pytest.approx(table["mean"][0])
    # The card carries the 95% interval of that forecast.
    assert card["range"]["lower"] == pytest.approx(table["lower"][0])
    assert card["range"]["lower"] < card["value"] < card["range"]["upper"]
    assert len(body["highlights"]) == 4


def test_history_respects_the_date_range(client, ready, saved_monthly):
    body = client.get("/api/history?start=2024-01&end=2024-12").get_json()
    assert [row["month"] for row in body["rows"]] == [f"2024-{m:02d}" for m in range(1, 13)]
    assert len(body["charts"]) == 4
    assert len(body["charts"][0]["figure"]["data"][0]["x"]) == 12
    assert len(client.get("/api/history").get_json()["rows"]) == len(saved_monthly)


def test_history_csv_download_respects_the_date_range(client, ready, saved_monthly):
    response = client.get("/api/history.csv?start=2025-01&end=2025-03")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "remittrend_2025-01_to_2025-03.csv" in response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).strip().splitlines()
    assert lines[0].split(",")[:2] == ["month", "cash_remittance_usd_million"]
    assert [line.split(",")[0] for line in lines[1:]] == ["2025-01", "2025-02", "2025-03"]
    assert float(lines[1].split(",")[1]) == pytest.approx(saved_monthly[TARGET]["2025-01"])


@pytest.mark.parametrize(
    "query", ["start=2025-06&end=2025-01", "start=2010-01", "end=2040-01", "start=June"]
)
def test_bad_date_ranges_are_rejected(client, ready, query):
    for route in ("history", "trends", "history.csv"):
        response = client.get(f"/api/{route}?{query}")
        assert response.status_code == 400


def test_trends_summarise_the_selected_period(client, ready, saved_monthly):
    body = client.get("/api/trends?start=2025-01&end=2025-12").get_json()
    cash = saved_monthly[TARGET]
    assert body["summary"]["months"] == 12
    assert body["summary"]["total"] == pytest.approx(cash[cash.index.year == 2025].sum())
    assert body["direction"]["direction"] in {"rising", "falling", "stable"}
    years = {row["year"]: row for row in body["annual"]}
    assert years[2019]["change_pct"] is None  # no 2018 in the dataset
    assert years[2025]["complete"]


def test_trends_match_the_proposal(client, ready, saved_vintage):
    body = client.get("/api/trends?start=2025-01&end=2025-12").get_json()
    years = {row["year"]: row for row in body["annual"]}
    assert body["summary"]["total"] == pytest.approx(35_630, abs=5)
    assert years[2025]["change_pct"] == pytest.approx(3.3, abs=0.05)  # proposal: +3.3% in 2025
    assert not years[2026]["complete"]


def test_relationships_page_reports_the_robustness_checks(client, ready):
    body = client.get("/api/relationships").get_json()
    sensitivity = body["sensitivity"]
    assert len(sensitivity["rows"]) == 3
    for row in sensitivity["rows"]:
        keys = [result["key"] for result in row["results"]]
        assert keys[:2] == ["whole", "recent"]
        assert set(keys) <= {"whole", "recent", "undifferenced"}
    verdicts = {
        bool(result["granger_significant_lags"])
        for row in sensitivity["rows"]
        for result in row["results"]
    }
    assert sensitivity["same_conclusion"] == (len(verdicts) == 1)
    for row in body["stationarity"]:
        assert row["level"]["verdict"] in {"stationary", "not stationary", "tests disagree"}
    for row in body["effect"]:
        assert row["improves_rolling"] == (row["rolling_with"] < row["rolling_without"])


def test_models_page_ranks_by_the_selection_rule(client, metrics):
    body = client.get("/api/models").get_json()
    column = metrics["selection"]["metric"]
    scores = [row[column] for row in body["models"]]
    assert scores == sorted(scores)
    best = body["models"][0]
    assert best["is_best"] and best["candidate"]
    assert best["key"] == body["best"]["key"] == body["selected"] == metrics["best_model"]
    assert best["p_value"] is None
    assert all(row["p_value"] is not None for row in body["models"][1:])
    assert body["selection"]["rule"] == config.MODEL_SELECTION
    assert body["selection"]["agree"] == (metrics["best_on_test"] == metrics["best_on_rolling"])
    assert body["selection"]["not_different"] == [
        row["name"] for row in body["models"] if row["candidate"] and row["different"] is False
    ]

    other = client.get("/api/models?model=sarima").get_json()
    assert other["selected"] == "sarima"
    assert "SARIMA" in other["charts"]["actual_vs_predicted"]["title"]
    assert client.get("/api/models?model=nope").status_code == 400


def test_models_csv_download(client, metrics):
    response = client.get("/api/models.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    lines = response.get_data(as_text=True).strip().splitlines()
    assert lines[0].startswith("model,main_model,")
    assert len(lines) == 1 + len(metrics["models"])
    assert lines[1].split(",")[1] == "True"  # the main model is listed first


def test_forecast_defaults_to_the_main_model_and_twelve_months(client, ready, saved_monthly):
    body = client.get("/api/forecast").get_json()
    assert body["horizon"] == 12
    assert len(body["rows"]) == 12
    assert body["rows"][0]["month"] == str(saved_monthly.index[-1] + 1)
    assert not body["assumptions"]["custom"]
    main = next(option for option in body["options"]["models"] if option["is_main"])
    assert body["model"]["key"] == main["key"]
    assert len(body["options"]["models"]) == 8
    # Every model's total for the same months, most accurate first.
    assert len(body["comparison"]) == 8
    assert body["comparison"][0]["is_main"]
    own = next(row for row in body["comparison"] if row["key"] == body["model"]["key"])
    assert own["total"] == pytest.approx(body["total"]["forecast"])


def test_every_model_forecasts_with_an_interval(client, ready):
    for key, method in [("sarima", "model"), ("xgb", "backtest"), ("rf_x", "backtest")]:
        body = client.get(f"/api/forecast?model={key}&horizon=6").get_json()
        assert len(body["rows"]) == 6
        assert body["model"]["has_intervals"]
        assert body["model"]["interval_method"] == method
        assert all(row["lower"] < row["forecast"] < row["upper"] for row in body["rows"])


def test_assumptions_change_only_models_that_use_the_indicators(client, ready):
    query = "horizon=12&exchange_rate=70&inflation=10"
    with_indicators = client.get(f"/api/forecast?model=sarimax&{query}").get_json()
    assert with_indicators["assumptions"]["custom"]
    assert with_indicators["assumptions"]["changed_forecast"]
    lag = with_indicators["assumptions"]["indicator_lag"]
    differences = [row["difference"] for row in with_indicators["rows"]]
    assert all(abs(d) < 1e-6 for d in differences[:lag])
    assert all(abs(d) > 1e-6 for d in differences[lag:])

    plain = client.get(f"/api/forecast?model=sarima&{query}").get_json()
    assert not plain["assumptions"]["changed_forecast"]
    assert plain["assumptions"]["range"] is None


def test_forecast_reports_values_outside_the_fitted_range(client, ready):
    inside = client.get("/api/forecast?model=xgb_x").get_json()["assumptions"]["range"]
    low, high = inside["inflation"]["trained"]
    assert low < high
    assert inside["inflation"]["outside"] == (not low <= inside["inflation"]["given"] <= high)

    extreme = client.get("/api/forecast?model=xgb_x&inflation=25&exchange_rate=110").get_json()
    limits = extreme["assumptions"]["range"]
    assert limits["inflation"]["given"] == 25
    assert limits["inflation"]["outside"]
    assert limits["exchange_rate_change"]["outside"]


def test_forecast_csv_download_matches_the_page(client, ready):
    query = "model=sarimax&horizon=6&exchange_rate=65"
    page = client.get(f"/api/forecast?{query}").get_json()
    response = client.get(f"/api/forecast.csv?{query}")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "remittrend_forecast_sarimax_" in response.headers["Content-Disposition"]
    lines = response.get_data(as_text=True).strip().splitlines()
    header = lines[0].split(",")
    assert header[:3] == ["month", "model", "forecast_usd_million"]
    assert len(lines) == 7
    first = dict(zip(header, lines[1].split(",")))
    assert float(first["forecast_usd_million"]) == pytest.approx(page["rows"][0]["forecast"])
    assert float(first["assumed_php_per_usd"]) == 65


@pytest.mark.parametrize(
    "query", ["model=nope", "horizon=5", "horizon=abc", "exchange_rate=abc", "exchange_rate=5", "inflation=99"]
)
def test_bad_forecast_requests_are_rejected(client, ready, query):
    for route in ("forecast", "forecast.csv"):
        response = client.get(f"/api/{route}?{query}")
        assert response.status_code == 400
        assert response.get_json()["message"]


def test_sources_page(client, ready, saved_monthly):
    body = client.get("/api/sources?year=2025").get_json()
    cash = saved_monthly[TARGET]
    assert body["complete"]
    assert body["total"] == pytest.approx(cash[cash.index.year == 2025].sum())
    assert body["countries"][0]["rank"] == 1
    assert sum(row["share"] for row in body["countries"]) <= 100
    assert client.get("/api/sources?year=2010").status_code == 400


def test_sources_match_the_proposal_for_2025(client, ready, saved_vintage):
    body = client.get("/api/sources?year=2025").get_json()
    assert body["total"] == pytest.approx(35_630, abs=5)
    top = body["countries"][:3]
    assert [row["country"] for row in top] == ["United States of America", "Singapore", "Saudi Arabia"]
    assert top[0]["share"] == pytest.approx(39.7, abs=0.05)
    year = next(row for row in body["yearly"] if row["year"] == 2025)
    assert year["land_based"] == pytest.approx(28_490, abs=5)
    assert year["sea_based"] == pytest.approx(7_140, abs=5)

    partial = client.get("/api/sources?year=2026").get_json()
    assert not partial["complete"]
    assert partial["period"] == "January–June 2026"
