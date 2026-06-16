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
    if request.endpoint == "shop.stripe_webhook":
        return

    expected = session.get(CSRF_SESSION_KEY)
    supplied = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
    )
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400, description="Invalid CSRF token.")


def validate_trusted_host() -> None:
    trusted_hosts = current_app.config.get("TRUSTED_HOSTS") or []
    if not trusted_hosts:
        return
    host = (request.host or "").split(":", 1)[0].rstrip(".").lower()
    if host not in trusted_hosts:
        abort(400, description="Untrusted Host header.")


def json_body() -> dict:
    raw_body = request.get_data(cache=True)
    if not raw_body:
        return {}
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Expected a valid JSON object.")
    return data


def is_safe_redirect(target: str | None) -> bool:
    if not target:
        return False
    if target != target.strip() or target.startswith("\\"):
        return False
    if any(ord(char) < 32 for char in target):
        return False
    base_url = current_app.config.get("PUBLIC_ORIGIN") or request.host_url
    if not base_url.endswith("/"):
        base_url += "/"
    test_url = urlparse(urljoin(base_url, target))
    ref_url = urlparse(base_url)
    if test_url.scheme not in {"http", "https"} or ref_url.netloc != test_url.netloc:
        return False
    if ref_url.scheme == "https" and test_url.scheme != "https":
        return False
    return True


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
        "img-src 'self' data: https://i.ytimg.com; "
        "media-src 'self'; "
        "connect-src 'self'; "
        "frame-src 'self' https://www.youtube-nocookie.com https://www.youtube.com https://player.twitch.tv; "
        "object-src 'none'; "
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
