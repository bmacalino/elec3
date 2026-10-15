"""JSON API consumed by the frontend. One route per dashboard page."""

from flask import Blueprint, Response, jsonify, request

from app import services
from remittrend.artifacts import to_plain

api = Blueprint("api", __name__)


def respond(payload: dict):
    # to_plain turns missing values (NaN) into null, which browsers can parse.
    return jsonify(to_plain(payload))


@api.errorhandler(services.NotReady)
def not_ready(error: services.NotReady):
    return jsonify(error="not_ready", message=str(error), missing=error.missing), 503


@api.errorhandler(services.BadRequest)
def bad_request(error: services.BadRequest):
    return jsonify(error="bad_request", message=str(error)), 400


@api.get("/status")
def status():
    return respond(services.pipeline_status())


@api.get("/overview")
def overview():
    return respond(services.overview())


@api.get("/history")
def history():
    return respond(services.history(request.args.get("start"), request.args.get("end")))


def download(text: str, filename: str) -> Response:
    return Response(
        text,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def forecast_arguments() -> tuple:
    return tuple(request.args.get(name) for name in ("model", "horizon", "exchange_rate", "inflation"))


@api.get("/history.csv")
def history_csv():
    return download(*services.history_csv(request.args.get("start"), request.args.get("end")))


@api.get("/models.csv")
def models_csv():
    return download(*services.models_csv())


@api.get("/forecast.csv")
def forecast_csv():
    return download(*services.forecast_csv(*forecast_arguments()))


@api.get("/trends")
def trends():
    return respond(services.trends(request.args.get("start"), request.args.get("end")))


@api.get("/seasonality")
def seasonality():
    return respond(services.seasonality())


@api.get("/relationships")
def relationships():
    return respond(services.relationships())


@api.get("/models")
def models():
    return respond(services.models(request.args.get("model")))


@api.get("/forecast")
def forecast():
    return respond(services.forecast(*forecast_arguments()))


@api.get("/sources")
def sources():
    return respond(services.sources(request.args.get("year")))
