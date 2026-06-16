"""App configuration."""
import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_STRIPE_PRICE_IDS = {
    "pulse_question": "price_1ThEuDDK6d8HY9tOVgZLFi6x",
    "support_ronpon": "price_1ThF8JDK6d8HY9tOjZohv915",
    "support_ronpon_bronze": "price_1ThFB7DK6d8HY9tOAwhvDmeq",
    "support_ronpon_silver": "price_1ThFBzDK6d8HY9tOSAZ9UzuP",
    "support_ronpon_gold": "price_1ThFClDK6d8HY9tOCp6zRZM5",
}


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def _csv_env(name: str) -> list[str]:
    return [
        value.strip().lower()
        for value in os.environ.get(name, "").split(",")
        if value.strip()
    ]


def _bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


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
    GOOGLE_CLIENT_ID = _env_first("GOOGLE_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _env_first("GOOGLE_CLIENT_SECRET", "GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_ALLOWED_DOMAINS = [
        d.strip().lower()
        for d in os.environ.get("GOOGLE_ALLOWED_DOMAINS", "").split(",")
        if d.strip()
    ]
    DISCORD_CLIENT_ID = _env_first("DISCORD_CLIENT_ID", "DISCORD_OAUTH_CLIENT_ID")
    DISCORD_CLIENT_SECRET = _env_first("DISCORD_CLIENT_SECRET", "DISCORD_OAUTH_CLIENT_SECRET")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PULSE_QUESTION_PRICE_ID = os.environ.get(
        "STRIPE_PULSE_QUESTION_PRICE_ID",
        DEFAULT_STRIPE_PRICE_IDS["pulse_question"],
    )
    STRIPE_SUPPORT_RONPON_PRICE_ID = os.environ.get(
        "STRIPE_SUPPORT_RONPON_PRICE_ID",
        DEFAULT_STRIPE_PRICE_IDS["support_ronpon"],
    )
    STRIPE_SUPPORT_RONPON_BRONZE_PRICE_ID = os.environ.get(
        "STRIPE_SUPPORT_RONPON_BRONZE_PRICE_ID",
        DEFAULT_STRIPE_PRICE_IDS["support_ronpon_bronze"],
    )
    STRIPE_SUPPORT_RONPON_SILVER_PRICE_ID = os.environ.get(
        "STRIPE_SUPPORT_RONPON_SILVER_PRICE_ID",
        DEFAULT_STRIPE_PRICE_IDS["support_ronpon_silver"],
    )
    STRIPE_SUPPORT_RONPON_GOLD_PRICE_ID = os.environ.get(
        "STRIPE_SUPPORT_RONPON_GOLD_PRICE_ID",
        DEFAULT_STRIPE_PRICE_IDS["support_ronpon_gold"],
    )
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    PUBLIC_ORIGIN = os.environ.get("PUBLIC_ORIGIN", "").rstrip("/")
    TRUSTED_HOSTS = _csv_env("TRUSTED_HOSTS") or None
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(4 * 1024 * 1024)))
    RATE_LIMIT_ENABLED = _bool_env("RATE_LIMIT_ENABLED", True)
    RATE_LIMIT_KEEP_SECONDS = int(os.environ.get("RATE_LIMIT_KEEP_SECONDS", str(24 * 60 * 60)))
    ENABLE_SCORES = _bool_env("ENABLE_SCORES", False)
    ENABLE_ACHIEVEMENTS = _bool_env("ENABLE_ACHIEVEMENTS", False)
    PREFERRED_URL_SCHEME = "https" if APP_ENV == "production" else "http"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_DURATION = timedelta(days=int(os.environ.get("REMEMBER_COOKIE_DAYS", "14")))
