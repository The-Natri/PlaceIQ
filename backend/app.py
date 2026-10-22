"""
Flask application factory. Kept as a factory (create_app) rather than a bare
module-level `app = Flask(...)` so tests can spin up isolated instances
later without import-order headaches.
"""
import datetime
import os

from flask import Flask, jsonify, send_from_directory
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import safe_join
from flask_cors import CORS

import db
from config import Config
from routes.analytics import analytics_bp
from routes.applications import applications_bp
from routes.auth import auth_bp
from routes.companies import companies_bp
from routes.departments import departments_bp
from routes.drives import drives_bp
from routes.offers import offers_bp
from routes.students import students_bp


class ISODateJSONProvider(DefaultJSONProvider):
    """
    Flask's default JSON provider serializes date/datetime as an RFC 2822
    string (e.g. "Sun, 10 Aug 2025 00:00:00 GMT") — a legacy holdover from
    HTTP header formatting, not what a JSON API's frontend expects. Every
    DATE/TIMESTAMP column in this schema (drive_date, applied_at,
    offer_date, ...) needs plain ISO 8601 instead, so this overrides the
    provider once here rather than converting dates by hand in every route.
    """
    @staticmethod
    def default(o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


def create_app():
    if not Config.JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Run start.ps1 / start.sh (or docker compose up), "
            "which generate one into a git-ignored file, or set it in .env."
        )

    # static_folder=None: the built frontend is served by spa() below, which
    # also handles client-side routes. Flask's default /static would not.
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.json = ISODateJSONProvider(app)

    # The UI is served from this same origin, so the browser needs no CORS.
    # Only if FRONTEND_ORIGINS is configured (a frontend hosted elsewhere) is
    # the API opened to those origins, and to nothing else.
    if Config.FRONTEND_ORIGINS:
        CORS(app, resources={r"/api/*": {"origins": Config.FRONTEND_ORIGINS}})

    db.init_pool()

    app.register_blueprint(auth_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(drives_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(offers_bp)
    app.register_blueprint(analytics_bp)

    @app.get("/api/health")
    def health():
        """Cheap liveness check that also proves the DB pool can connect."""
        with db.get_cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return jsonify({"status": "ok"})

    @app.route("/api/<path:_>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def api_not_found(_):
        """An unknown API path is a JSON 404, never the HTML page below."""
        return jsonify({"error": "Not found"}), 404

    dist = os.path.abspath(Config.FRONTEND_DIST)

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path):
        """
        Serves the built React app. A path that is a real file (a script,
        a stylesheet, the favicon) is sent as-is. Anything else is a
        client-side route like /admin/drives/24, so it gets index.html and
        React Router renders the right page. That is what makes refreshing
        the browser on any page work.
        """
        index = os.path.join(dist, "index.html")
        if not os.path.isfile(index):
            return jsonify({"error": f"Frontend not built: {index} is missing. Run npm run build in frontend/."}), 503
        # safe_join returns None for anything that escapes dist (../.env),
        # so such a path is never even looked at on disk.
        requested = safe_join(dist, path) if path else None
        if requested and os.path.isfile(requested):
            # Vite names built assets by content hash, so they can be cached for good.
            max_age = 31536000 if path.startswith("assets/") else 0
            return send_from_directory(dist, path, max_age=max_age)
        response = send_from_directory(dist, "index.html", max_age=0)
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app


if __name__ == "__main__":
    # The production server. See serve.py.
    import serve
    serve.main()
