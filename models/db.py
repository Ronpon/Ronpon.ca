"""Database connection layer — PostgreSQL (production) or SQLite (local dev).

Usage:
    from models.db import get_conn, init_db
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT ...")
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")

_pg = None
if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        _pg = psycopg2
    except ImportError:
        pass

_SQLITE_PATH: Optional[str] = None  # set by init_db()


def ph(n: int = 1) -> str:
    """Return n placeholders for the active backend (%s or ?)."""
    p = "%s" if (_pg and DATABASE_URL) else "?"
    return ", ".join([p] * n)


@contextmanager
def get_conn():
    """Yield a DB-API 2.0 connection. Commits on success, closes always."""
    if _pg and DATABASE_URL:
        conn = _pg.connect(
            DATABASE_URL, sslmode="require",
            cursor_factory=_pg.extras.DictCursor,
        )
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db(app_config) -> None:
    """Create tables if they don't exist. Call once at startup."""
    global _SQLITE_PATH
    _SQLITE_PATH = app_config.SQLITE_PATH

    with get_conn() as conn:
        cur = conn.cursor()

        # ── Users ───────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                email       TEXT    NOT NULL UNIQUE,
                pw_hash     TEXT    NOT NULL,
                is_admin    INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                username    TEXT    NOT NULL UNIQUE,
                email       TEXT    NOT NULL UNIQUE,
                pw_hash     TEXT    NOT NULL,
                is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        # ── Videos ──────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                youtube_id  TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                category    TEXT    NOT NULL DEFAULT 'Uncategorized',
                added_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id          SERIAL PRIMARY KEY,
                youtube_id  TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                category    TEXT    NOT NULL DEFAULT 'Uncategorized',
                added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        # ── Polls (The Pulse) ───────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question    TEXT    NOT NULL,
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id          SERIAL PRIMARY KEY,
                question    TEXT    NOT NULL,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                label       TEXT    NOT NULL
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id          SERIAL PRIMARY KEY,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                label       TEXT    NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                voted_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(poll_id, user_id)
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_votes (
                id          SERIAL PRIMARY KEY,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                voted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(poll_id, user_id)
            )
        """)

        # ── High Scores ────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS high_scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                game        TEXT    NOT NULL,
                score       INTEGER NOT NULL,
                detail      TEXT    NOT NULL DEFAULT '',
                achieved_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS high_scores (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                game        TEXT    NOT NULL,
                score       INTEGER NOT NULL,
                detail      TEXT    NOT NULL DEFAULT '',
                achieved_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        # ── Pulse Videos (Game Show & Podcast episodes) ─────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pulse_videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                youtube_id  TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                section     TEXT    NOT NULL DEFAULT 'game-show',
                added_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS pulse_videos (
                id          SERIAL PRIMARY KEY,
                youtube_id  TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                section     TEXT    NOT NULL DEFAULT 'game-show',
                added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        # ── Pulse Settings (key-value for Live Now, etc.) ───────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pulse_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)

        conn.commit()
