"""App configuration."""
import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))
    INSECURE_DEV_SECRET = "ronpon-dev-secret-change-me"
    SECRET_KEY = os.environ.get("SECRET_KEY") or (
        INSECURE_DEV_SECRET if APP_ENV != "production" else None
    )
    DATABASE_URL = os.environ.get("DATABASE_URL")
    SQLITE_PATH = os.path.join(BASE_DIR, "ronpon.db")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "ron")
    ADMIN_SETUP_TOKEN = os.environ.get("ADMIN_SETUP_TOKEN", "")
    ADMIN_PASSWORD_MIN_LENGTH = int(os.environ.get("ADMIN_PASSWORD_MIN_LENGTH", "12"))
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_ALLOWED_DOMAINS = [
        d.strip().lower()
        for d in os.environ.get("GOOGLE_ALLOWED_DOMAINS", "").split(",")
        if d.strip()
    ]
    PREFERRED_URL_SCHEME = "https" if APP_ENV == "production" else "http"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_DURATION = timedelta(days=int(os.environ.get("REMEMBER_COOKIE_DAYS", "14")))
