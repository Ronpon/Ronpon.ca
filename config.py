"""App configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "ronpon-dev-secret-change-me")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    SQLITE_PATH = os.path.join(BASE_DIR, "ronpon.db")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "ron")
