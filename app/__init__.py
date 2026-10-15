"""Flask application: the JSON API under /api, plus the built frontend."""

from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from app.routes.api import api

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app(frontend_dist: Path = FRONTEND_DIST) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.register_blueprint(api, url_prefix="/api")

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            return jsonify(error="Unknown API route."), 404
        # Built files (JS, CSS, fonts) are served as they are. Every other path
        # gets index.html so that React Router can show the right page.
        if path and (frontend_dist / path).is_file():
            return send_from_directory(frontend_dist, path)
        if "." in path.rsplit("/", 1)[-1]:
            # A file that is not in the build, not a page.
            return "Not found.", 404
        if not (frontend_dist / "index.html").is_file():
            return (
                "The frontend has not been built yet. "
                "Run: npm --prefix frontend run build",
                503,
            )
        return send_from_directory(frontend_dist, "index.html")

    return app
