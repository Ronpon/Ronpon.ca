"""Small security helpers shared by the Flask app."""
from __future__ import annotations

import hmac
import secrets
from urllib.parse import urlparse, urljoin

from flask import abort, current_app, request, session


CSRF_SESSION_KEY = "_csrf_token"


def csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return

    expected = session.get(CSRF_SESSION_KEY)
    supplied = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
    )
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400, description="Invalid CSRF token.")


def is_safe_redirect(target: str | None) -> bool:
    if not target:
        return False
    host_url = request.host_url
    test_url = urlparse(urljoin(host_url, target))
    ref_url = urlparse(host_url)
    return test_url.scheme in {"http", "https"} and ref_url.netloc == test_url.netloc


def require_configured_secret(app=None) -> None:
    flask_app = app or current_app
    secret = flask_app.config.get("SECRET_KEY")
    insecure = flask_app.config.get("INSECURE_DEV_SECRET")
    if not secret or (flask_app.config.get("APP_ENV") == "production" and secret == insecure):
        raise RuntimeError("Set a strong SECRET_KEY before running in production.")


def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "media-src 'self'; "
        "connect-src 'self'; "
        "frame-src https://www.youtube-nocookie.com https://www.youtube.com https://player.twitch.tv; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'",
    )
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response
