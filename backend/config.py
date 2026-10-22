"""
Central config loaded from environment variables (see .env.example at repo
root). Keeping this in one module means every route/service reads settings
the same way instead of scattering os.environ.get() calls throughout.
"""
import os

from dotenv import load_dotenv

# Load the repo-root .env regardless of which directory Flask is started
# from, so `flask run` from backend/ and a container both work the same way.
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, "..", ".env"))


class Config:
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://placement_admin:placement_dev_password@localhost:5432/placement_db",
    )
    # No default on purpose. A known fallback secret would let anyone forge a
    # login token, so the app refuses to start without one (see create_app).
    # start.ps1 / start.sh and the Docker entrypoint generate a random one into
    # a git-ignored file the first time.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
    if JWT_SECRET_KEY == "replace_with_a_long_random_secret":  # .env.example's placeholder
        JWT_SECRET_KEY = ""
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = 12
    ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:6000")

    # Off unless explicitly switched on: Flask's debugger lets anyone who can
    # reach the server run arbitrary Python, so it must never be the default.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # The UI and the API are served from the same origin (one port), so the
    # browser needs no CORS at all and none is allowed by default. Setting
    # FRONTEND_ORIGINS (comma-separated) opens the API to those origins only,
    # e.g. for a separately hosted frontend.
    FRONTEND_ORIGINS = [
        origin.strip()
        for origin in os.environ.get("FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    ]

    # One port for the UI and the API. 127.0.0.1 by default: nothing outside
    # this machine can connect unless HOST is set (the Docker image sets
    # 0.0.0.0 inside its container, and compose publishes only to localhost).
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "8080"))

    # The built React app (npm run build). The Docker image puts it here too.
    FRONTEND_DIST = os.environ.get(
        "FRONTEND_DIST", os.path.join(_here, "..", "frontend", "dist")
    )
