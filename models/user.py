"""User model with Flask-Login integration."""
from __future__ import annotations

from typing import Optional
from flask import current_app
from flask_login import UserMixin
from flask_bcrypt import generate_password_hash, check_password_hash

from models.db import get_conn, ph


class User(UserMixin):
    """Lightweight user object — loaded from DB rows, not an ORM."""

    def __init__(self, id: int, username: str, email: str,
                 pw_hash: str, is_admin: bool, created_at: str):
        self.id = id
        self.username = username
        self.email = email
        self.pw_hash = pw_hash
        self.is_admin = bool(is_admin)
        self.created_at = created_at

    # ── Lookups ─────────────────────────────────────────────────

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

    # ── Create ──────────────────────────────────────────────────

    @staticmethod
    def create(username: str, email: str, password: str) -> "User":
        pw_hash = generate_password_hash(password).decode("utf-8")
        admin_username = current_app.config.get("ADMIN_USERNAME", "")
        is_admin = bool(admin_username and username == admin_username)
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO users (username, email, pw_hash, is_admin) "
                f"VALUES ({ph(4)})",
                (username, email, pw_hash, is_admin),
            )
            conn.commit()
        return User.get_by_username(username)

    # ── Password check ──────────────────────────────────────────

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.pw_hash, password)

    # ── Internal ────────────────────────────────────────────────

    @staticmethod
    def _from_row(row) -> "User":
        # sqlite3.Row supports dict-style access; psycopg2 tuples do not
        if hasattr(row, "keys"):
            return User(
                id=row["id"], username=row["username"], email=row["email"],
                pw_hash=row["pw_hash"], is_admin=row["is_admin"],
                created_at=str(row["created_at"]),
            )
        # psycopg2 tuple — column order matches CREATE TABLE
        return User(
            id=row[0], username=row[1], email=row[2],
            pw_hash=row[3], is_admin=row[4], created_at=str(row[5]),
        )


def sqlite3_Row_type():
    import sqlite3
    return sqlite3.Row
