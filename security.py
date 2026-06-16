"""Small security helpers shared by the Flask app."""
from __future__ import annotations

import time
from functools import wraps
import hmac
import secrets
from typing import Callable
from urllib.parse import urlparse, urljoin

from flask import abort, current_app, jsonify, request, session


CSRF_SESSION_KEY = "_csrf_token"
_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS = 60 * 60
_last_rate_limit_cleanup = 0.0


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


def rate_limit(scope: str, limit: int, window_seconds: int, *, key_func: Callable[[], str] | None = None):
    """Apply a database-backed fixed-window rate limit to a Flask route."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            check_rate_limit(scope, limit, window_seconds, key_func=key_func)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def check_rate_limit(
    scope: str,
    limit: int,
    window_seconds: int,
    *,
    key_func: Callable[[], str] | None = None,
) -> None:
    if not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return
    if limit <= 0 or window_seconds <= 0:
        return

    now = int(time.time())
    window_start = now - (now % window_seconds)
    identifier = key_func() if key_func else _client_ip()
    rate_key = f"{scope}:{identifier}"
    count = _increment_rate_limit(rate_key, window_start)
    if count > limit:
        retry_after = window_seconds - (now - window_start)
        _abort_rate_limited(retry_after)


def _client_ip() -> str:
    return (request.remote_addr or "unknown").strip().lower()


def _increment_rate_limit(rate_key: str, window_start: int) -> int:
    from models.db import get_conn, is_postgres, ph

    now = int(time.time())
    with get_conn() as conn:
        cur = conn.cursor()
        if is_postgres():
            cur.execute(
                f"""
                INSERT INTO rate_limits (rate_key, window_start, count, updated_at)
                VALUES ({ph(3)}, now())
                ON CONFLICT (rate_key) DO UPDATE
                SET count = CASE
                        WHEN rate_limits.window_start = EXCLUDED.window_start
                        THEN rate_limits.count + 1
                        ELSE 1
                    END,
                    window_start = EXCLUDED.window_start,
                    updated_at = now()
                RETURNING count
                """,
                (rate_key, window_start, 1),
            )
            count = int(cur.fetchone()[0])
        else:
            cur.execute(f"SELECT window_start, count FROM rate_limits WHERE rate_key = {ph()}", (rate_key,))
            row = cur.fetchone()
            if row and int(row["window_start"]) == window_start:
                count = int(row["count"]) + 1
                cur.execute(
                    f"UPDATE rate_limits SET count = {ph()}, updated_at = {ph()} WHERE rate_key = {ph()}",
                    (count, str(now), rate_key),
                )
            else:
                count = 1
                cur.execute(
                    f"""
                    INSERT OR REPLACE INTO rate_limits (rate_key, window_start, count, updated_at)
                    VALUES ({ph(4)})
                    """,
                    (rate_key, window_start, count, str(now)),
                )
        _cleanup_rate_limits(cur, now)
        return count


def _cleanup_rate_limits(cur, now: int) -> None:
    global _last_rate_limit_cleanup
    if now - _last_rate_limit_cleanup < _RATE_LIMIT_CLEANUP_INTERVAL_SECONDS:
        return
    _last_rate_limit_cleanup = float(now)
    cutoff = now - int(current_app.config.get("RATE_LIMIT_KEEP_SECONDS", 24 * 60 * 60))
    from models.db import ph

    cur.execute(f"DELETE FROM rate_limits WHERE window_start < {ph()}", (cutoff,))


def _abort_rate_limited(retry_after: int) -> None:
    message = "Too many requests. Please try again later."
    wants_json = request.is_json or request.path.startswith(("/games/werblers/api/", "/games/party/api/"))
    if wants_json:
        response = jsonify({"error": message})
        response.status_code = 429
    else:
        response = current_app.response_class(message, status=429, mimetype="text/plain")
    response.headers["Retry-After"] = str(max(1, retry_after))
    abort(response)


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
