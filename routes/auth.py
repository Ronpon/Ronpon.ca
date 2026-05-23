"""Auth routes for admin setup, admin password login, and profile actions."""
from __future__ import annotations

import time
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_bcrypt import generate_password_hash
from flask_login import current_user, login_required, login_user, logout_user

from models.db import get_conn, ph
from models.user import User
from security import is_safe_redirect

auth_bp = Blueprint("auth", __name__)

_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_ATTEMPTS = 8
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
_DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
_DISCORD_USER_URL = "https://discord.com/api/users/@me"


def _rate_limit_key(username: str) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    remote_ip = forwarded_for.split(",", 1)[0].strip() or request.remote_addr or "unknown"
    return f"{remote_ip}:{username.lower()}"


def _too_many_login_attempts(username: str) -> bool:
    now = time.time()
    key = _rate_limit_key(username)
    attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if now - ts < _LOGIN_WINDOW_SECONDS]
    _LOGIN_ATTEMPTS[key] = attempts
    return len(attempts) >= _LOGIN_MAX_ATTEMPTS


def _record_failed_login(username: str) -> None:
    _LOGIN_ATTEMPTS.setdefault(_rate_limit_key(username), []).append(time.time())


def _clear_failed_logins(username: str) -> None:
    _LOGIN_ATTEMPTS.pop(_rate_limit_key(username), None)


def _admin_setup_allowed() -> bool:
    if User.count() > 0:
        return False
    token = current_app.config.get("ADMIN_SETUP_TOKEN", "")
    if not token:
        return current_app.config.get("APP_ENV") != "production"
    supplied = request.args.get("setup_token") or request.form.get("setup_token")
    return supplied == token


def _oauth_next() -> str:
    next_page = request.args.get("next") or session.pop("oauth_next", None)
    return next_page if is_safe_redirect(next_page) else url_for("main.home")


def _google_configured() -> bool:
    return bool(current_app.config.get("GOOGLE_CLIENT_ID") and current_app.config.get("GOOGLE_CLIENT_SECRET"))


def _discord_configured() -> bool:
    return bool(current_app.config.get("DISCORD_CLIENT_ID") and current_app.config.get("DISCORD_CLIENT_SECRET"))


def _external_url(endpoint: str) -> str:
    scheme = current_app.config.get("PREFERRED_URL_SCHEME") or request.scheme
    return url_for(endpoint, _external=True, _scheme=scheme)


def _google_redirect_uri() -> str:
    return _external_url("auth.google_callback")


def _discord_redirect_uri() -> str:
    return _external_url("auth.discord_callback")


def _http_post_json(url: str, payload: dict) -> dict:
    body = urlencode(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    request_url = f"{url}?{urlencode(params)}" if params else url
    req = Request(request_url, headers=headers or {})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _validate_google_identity(id_token: str) -> dict:
    info = _http_get_json(_GOOGLE_TOKENINFO_URL, {"id_token": id_token})
    client_id = current_app.config["GOOGLE_CLIENT_ID"]
    if info.get("aud") != client_id:
        raise ValueError("Invalid Google token audience.")
    if info.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Invalid Google token issuer.")
    if info.get("email_verified") not in {"true", True}:
        raise ValueError("Google email is not verified.")
    email = (info.get("email") or "").lower()
    allowed_domains = current_app.config.get("GOOGLE_ALLOWED_DOMAINS", [])
    if allowed_domains and email.rsplit("@", 1)[-1] not in allowed_domains:
        raise ValueError("Email domain is not allowed.")
    if not info.get("sub") or not email:
        raise ValueError("Google identity response is missing required fields.")
    return info


def _fetch_discord_identity(access_token: str) -> dict:
    info = _http_get_json(_DISCORD_USER_URL, headers={"Authorization": f"Bearer {access_token}"})
    email = (info.get("email") or "").lower()
    if not info.get("id") or not email:
        raise ValueError("Discord identity response is missing required fields.")
    if info.get("verified") is False:
        raise ValueError("Discord email is not verified.")
    return info


def _store_oauth_state() -> str:
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    next_page = request.args.get("next")
    if is_safe_redirect(next_page):
        session["oauth_next"] = next_page
    return state


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # First-run admin setup only. Public users should use OAuth providers.
    if not _admin_setup_allowed():
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        admin_username = current_app.config.get("ADMIN_USERNAME", "")
        min_password_length = current_app.config.get("ADMIN_PASSWORD_MIN_LENGTH", 12)

        errors = []
        if username != admin_username:
            errors.append("Username must match the configured admin username.")
        if not email or "@" not in email:
            errors.append("Enter a valid email.")
        if len(password) < min_password_length:
            errors.append(f"Password must be at least {min_password_length} characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.get_by_username(username):
            errors.append("Username already taken.")
        if User.get_by_email(email):
            errors.append("Email already registered.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/register.html", username=username, email=email)

        user = User.create(username, email, password)
        login_user(user, fresh=True)
        flash("Admin account created.", "success")
        return redirect(url_for("main.home"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if _too_many_login_attempts(username):
            flash("Too many failed login attempts. Please try again later.", "error")
            return render_template("auth/login.html", username=username), 429

        user = User.get_by_username(username)
        if user and user.is_admin and user.check_password(password):
            remember = bool(request.form.get("remember"))
            login_user(user, remember=remember, fresh=True)
            _clear_failed_logins(username)
            next_page = request.args.get("next")
            flash("Logged in.", "success")
            return redirect(next_page if is_safe_redirect(next_page) else url_for("main.home"))

        _record_failed_login(username)
        flash("Invalid username or password.", "error")
        return render_template("auth/login.html", username=username)

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/social/<provider>")
def social_login(provider):
    if provider == "google":
        if not _google_configured():
            flash("Google login is not configured yet.", "error")
            return redirect(url_for("auth.login"))
        state = _store_oauth_state()
        nonce = secrets.token_urlsafe(32)
        session["oauth_nonce"] = nonce
        params = {
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "redirect_uri": _google_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
        return redirect(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")

    if provider == "discord":
        if not _discord_configured():
            flash("Discord login is not configured yet.", "error")
            return redirect(url_for("auth.login"))
        params = {
            "client_id": current_app.config["DISCORD_CLIENT_ID"],
            "redirect_uri": _discord_redirect_uri(),
            "response_type": "code",
            "scope": "identify email",
            "state": _store_oauth_state(),
            "prompt": "consent",
        }
        return redirect(f"{_DISCORD_AUTH_URL}?{urlencode(params)}")

    flash(f"{provider.title()} login is not configured yet.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth/google/callback")
def google_callback():
    if request.args.get("error"):
        flash("Google login was cancelled.", "error")
        return redirect(url_for("auth.login"))

    expected_state = session.pop("oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        abort(400, description="Invalid OAuth state.")

    code = request.args.get("code")
    if not code or not _google_configured():
        flash("Google login is not configured correctly.", "error")
        return redirect(url_for("auth.login"))

    try:
        token_data = _http_post_json(_GOOGLE_TOKEN_URL, {
            "code": code,
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": _google_redirect_uri(),
            "grant_type": "authorization_code",
        })
        identity = _validate_google_identity(token_data.get("id_token", ""))
    except Exception:
        current_app.logger.exception("Google OAuth login failed")
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for("auth.login"))

    nonce = session.pop("oauth_nonce", None)
    if nonce and identity.get("nonce") and identity.get("nonce") != nonce:
        abort(400, description="Invalid OAuth nonce.")

    user = User.create_or_update_oauth(
        provider="google",
        subject=identity["sub"],
        email=identity["email"],
        name=identity.get("name") or identity["email"].split("@", 1)[0],
    )
    login_user(user, fresh=True)
    flash("Logged in with Google.", "success")
    return redirect(_oauth_next())


@auth_bp.route("/auth/discord/callback")
def discord_callback():
    if request.args.get("error"):
        flash("Discord login was cancelled.", "error")
        return redirect(url_for("auth.login"))

    expected_state = session.pop("oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        abort(400, description="Invalid OAuth state.")

    code = request.args.get("code")
    if not code or not _discord_configured():
        flash("Discord login is not configured correctly.", "error")
        return redirect(url_for("auth.login"))

    try:
        token_data = _http_post_json(_DISCORD_TOKEN_URL, {
            "code": code,
            "client_id": current_app.config["DISCORD_CLIENT_ID"],
            "client_secret": current_app.config["DISCORD_CLIENT_SECRET"],
            "redirect_uri": _discord_redirect_uri(),
            "grant_type": "authorization_code",
        })
        identity = _fetch_discord_identity(token_data.get("access_token", ""))
    except Exception:
        current_app.logger.exception("Discord OAuth login failed")
        flash("Discord login failed. Please try again.", "error")
        return redirect(url_for("auth.login"))

    user = User.create_or_update_oauth(
        provider="discord",
        subject=identity["id"],
        email=identity["email"],
        name=identity.get("global_name") or identity.get("username") or identity["email"].split("@", 1)[0],
    )
    login_user(user, fresh=True)
    flash("Logged in with Discord.", "success")
    return redirect(_oauth_next())


@auth_bp.route("/profile")
@login_required
def profile():
    return render_template("auth/profile.html")


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")
    min_password_length = current_app.config.get("ADMIN_PASSWORD_MIN_LENGTH", 12)

    if not current_user.check_password(current_pw):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("auth.profile"))

    if len(new_pw) < min_password_length:
        flash(f"New password must be at least {min_password_length} characters.", "error")
        return redirect(url_for("auth.profile"))

    if new_pw != confirm_pw:
        flash("New passwords do not match.", "error")
        return redirect(url_for("auth.profile"))

    pw_hash = generate_password_hash(new_pw).decode("utf-8")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE users SET pw_hash = {ph()} WHERE id = {ph()}",
            (pw_hash, current_user.id),
        )

    logout_user()
    flash("Password updated. Please log in again.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")

    if not current_user.check_password(password):
        flash("Incorrect password.", "error")
        return redirect(url_for("auth.profile"))

    user_id = current_user.id
    logout_user()

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM poll_submissions WHERE user_id = {ph()}", (user_id,))
        cur.execute(f"DELETE FROM poll_votes WHERE user_id = {ph()}", (user_id,))
        cur.execute(f"DELETE FROM users WHERE id = {ph()}", (user_id,))

    flash("Your account has been deleted.", "success")
    return redirect(url_for("main.home"))
