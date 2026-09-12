"""
Flask application factory. Kept as a factory (create_app) rather than a bare
module-level `app = Flask(...)` so tests can spin up isolated instances
later without import-order headaches.
"""
import datetime

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
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
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json = ISODateJSONProvider(app)

    # Wide-open CORS for local dev: frontend runs on a different port
    # (Vite default 5173) than the API (5000). Tighten this to a specific
    # origin before any real deployment.
    CORS(app)

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

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=Config.DEBUG, port=5000)
