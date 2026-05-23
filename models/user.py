"""User model with Flask-Login integration."""
from __future__ import annotations

import re
from typing import Optional

from flask import current_app
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import UserMixin

from models.db import get_conn, ph


class User(UserMixin):
    """Lightweight user object loaded from DB rows."""

    def __init__(
        self,
        id: int,
        username: str,
        email: str,
        pw_hash: str,
        is_admin: bool,
        created_at: str,
        oauth_provider: str = "",
        oauth_sub: str = "",
        display_name: str = "",
    ):
        self.id = id
        self.username = username
        self.email = email
        self.pw_hash = pw_hash
        self.is_admin = bool(is_admin)
        self.created_at = created_at
        self.oauth_provider = oauth_provider or ""
        self.oauth_sub = oauth_sub or ""
        self.display_name = display_name or username

    @staticmethod
    def get_by_id(user_id: int) -> Optional["User"]:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE id = {ph()}", (user_id,))
            row = cur.fetchone()
        return User._from_row(row) if row else None

    @staticmethod
    def get_by_username(username: str) -> Optional["User"]:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE username = {ph()}", (username,))
            row = cur.fetchone()
        return User._from_row(row) if row else None

    @staticmethod
    def get_by_email(email: str) -> Optional["User"]:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM users WHERE email = {ph()}", (email,))
            row = cur.fetchone()
        return User._from_row(row) if row else None

    @staticmethod
    def get_by_oauth(provider: str, subject: str) -> Optional["User"]:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM users WHERE oauth_provider = {ph()} AND oauth_sub = {ph()}",
                (provider, subject),
            )
            row = cur.fetchone()
        return User._from_row(row) if row else None

    @staticmethod
    def count() -> int:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]

    @staticmethod
    def create(username: str, email: str, password: str) -> "User":
        pw_hash = generate_password_hash(password).decode("utf-8")
        admin_username = current_app.config.get("ADMIN_USERNAME", "")
        is_admin = bool(admin_username and username == admin_username)
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO users (username, email, pw_hash, is_admin, display_name) "
                f"VALUES ({ph(5)})",
                (username, email, pw_hash, is_admin, username),
            )
        return User.get_by_username(username)

    @staticmethod
    def create_or_update_oauth(provider: str, subject: str, email: str, name: str) -> "User":
        email = email.strip().lower()
        name = (name or email.split("@", 1)[0]).strip()

        existing = User.get_by_oauth(provider, subject)
        if existing:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE users SET email = {ph()}, display_name = {ph()} WHERE id = {ph()}",
                    (email, name, existing.id),
                )
            return User.get_by_id(existing.id)

        by_email = User.get_by_email(email)
        if by_email:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE users SET oauth_provider = {ph()}, oauth_sub = {ph()}, display_name = {ph()} WHERE id = {ph()}",
                    (provider, subject, name, by_email.id),
                )
            return User.get_by_id(by_email.id)

        username = User._unique_username(email, name)
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO users (username, email, pw_hash, is_admin, oauth_provider, oauth_sub, display_name) "
                f"VALUES ({ph(7)})",
                (username, email, "!oauth", False, provider, subject, name),
            )
        return User.get_by_oauth(provider, subject)

    @staticmethod
    def _unique_username(email: str, name: str) -> str:
        base = name or email.split("@", 1)[0]
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-_").lower()
        if len(base) < 3:
            base = "user"
        candidate = base[:30]
        suffix = 1
        while User.get_by_username(candidate):
            suffix_text = f"-{suffix}"
            candidate = f"{base[:30 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        return candidate

    def check_password(self, password: str) -> bool:
        if not self.pw_hash or self.pw_hash.startswith("!"):
            return False
        return check_password_hash(self.pw_hash, password)

    @staticmethod
    def _from_row(row) -> "User":
        if hasattr(row, "keys"):
            keys = row.keys()
            return User(
                id=row["id"],
                username=row["username"],
                email=row["email"],
                pw_hash=row["pw_hash"],
                is_admin=row["is_admin"],
                created_at=str(row["created_at"]),
                oauth_provider=row["oauth_provider"] if "oauth_provider" in keys else "",
                oauth_sub=row["oauth_sub"] if "oauth_sub" in keys else "",
                display_name=row["display_name"] if "display_name" in keys else "",
            )
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            pw_hash=row[3],
            is_admin=row[4],
            oauth_provider=row[5] if len(row) > 6 else "",
            oauth_sub=row[6] if len(row) > 7 else "",
            display_name=row[7] if len(row) > 8 else "",
            created_at=str(row[8] if len(row) > 8 else row[5]),
        )


def sqlite3_Row_type():
    import sqlite3
    return sqlite3.Row
