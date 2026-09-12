"""
Flask application factory. Kept as a factory (create_app) rather than a bare
module-level `app = Flask(...)` so tests can spin up isolated instances
later without import-order headaches.
"""
from flask import Flask, jsonify
from flask_cors import CORS

import db
from config import Config
from routes.auth import auth_bp
from routes.companies import companies_bp
from routes.departments import departments_bp
from routes.drives import drives_bp
from routes.students import students_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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
