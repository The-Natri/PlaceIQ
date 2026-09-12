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
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev_secret_change_me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = 12
    ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:6000")
    DEBUG = os.environ.get("FLASK_ENV", "development") == "development"
