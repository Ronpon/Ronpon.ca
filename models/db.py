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


def is_postgres() -> bool:
    """Return whether the active database connection uses PostgreSQL."""
    return bool(_pg and DATABASE_URL)


def _column_exists(cur, table: str, column: str) -> bool:
    if _pg and DATABASE_URL:
        cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        return cur.fetchone() is not None
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _ensure_column(cur, table: str, column: str, definition: str) -> None:
    if not _column_exists(cur, table, column):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
                oauth_provider TEXT NOT NULL DEFAULT '',
                oauth_sub   TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                username    TEXT    NOT NULL UNIQUE,
                email       TEXT    NOT NULL UNIQUE,
                pw_hash     TEXT    NOT NULL,
                is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
                oauth_provider TEXT NOT NULL DEFAULT '',
                oauth_sub   TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        _ensure_column(cur, "users", "oauth_provider", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(cur, "users", "oauth_sub", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(cur, "users", "display_name", "TEXT NOT NULL DEFAULT ''")

        # Rate limit counters for public routes that create server work.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                rate_key     TEXT PRIMARY KEY,
                window_start INTEGER NOT NULL,
                count        INTEGER NOT NULL DEFAULT 0,
                updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                rate_key     TEXT PRIMARY KEY,
                window_start BIGINT NOT NULL,
                count        INTEGER NOT NULL DEFAULT 0,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start)")

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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS video_playlists (
                name        TEXT PRIMARY KEY,
                sort_order  INTEGER NOT NULL DEFAULT 0
            )
        """)

        # ── Polls (The Pulse) ───────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question    TEXT    NOT NULL,
                title       TEXT    NOT NULL DEFAULT '',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id          SERIAL PRIMARY KEY,
                question    TEXT    NOT NULL,
                title       TEXT    NOT NULL DEFAULT '',
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        _ensure_column(cur, "polls", "title", "TEXT NOT NULL DEFAULT ''")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_questions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id        INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                question_text  TEXT    NOT NULL,
                question_order INTEGER NOT NULL DEFAULT 0
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_questions (
                id             SERIAL PRIMARY KEY,
                poll_id        INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                question_text  TEXT    NOT NULL,
                question_order INTEGER NOT NULL DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                question_id INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE,
                label       TEXT    NOT NULL
                , option_order INTEGER NOT NULL DEFAULT 0
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id          SERIAL PRIMARY KEY,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                question_id INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE,
                label       TEXT    NOT NULL
                , option_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        _ensure_column(cur, "poll_options", "question_id", "INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE")
        _ensure_column(cur, "poll_options", "option_order", "INTEGER NOT NULL DEFAULT 0")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                question_id INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE,
                option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                voted_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_votes (
                id          SERIAL PRIMARY KEY,
                poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                question_id INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE,
                option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                voted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        if _pg and DATABASE_URL:
            cur.execute("ALTER TABLE poll_votes DROP CONSTRAINT IF EXISTS poll_votes_poll_id_user_id_key")
        else:
            cur.execute("PRAGMA index_list(poll_votes)")
            indexes = cur.fetchall()
            has_legacy_unique = any(row[2] and str(row[1]).startswith("sqlite_autoindex_poll_votes") for row in indexes)
            if has_legacy_unique:
                cur.execute("ALTER TABLE poll_votes RENAME TO poll_votes_legacy")
                cur.execute("""
                    CREATE TABLE poll_votes (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        poll_id     INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                        question_id INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE,
                        option_id   INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
                        user_id     INTEGER NOT NULL REFERENCES users(id),
                        voted_at    TEXT    NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                cur.execute("""
                    INSERT INTO poll_votes (id, poll_id, option_id, user_id, voted_at)
                    SELECT id, poll_id, option_id, user_id, voted_at FROM poll_votes_legacy
                """)
                cur.execute("DROP TABLE poll_votes_legacy")
        _ensure_column(cur, "poll_votes", "question_id", "INTEGER REFERENCES poll_questions(id) ON DELETE CASCADE")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_submissions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id      INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                submitted_at TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(poll_id, user_id)
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS poll_submissions (
                id           SERIAL PRIMARY KEY,
                poll_id      INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(poll_id, user_id)
            )
        """)

        # Migrate old single-question polls into the multi-question shape.
        cur.execute("UPDATE polls SET title = question WHERE title = ''")
        cur.execute("""
            SELECT p.id, p.question
            FROM polls p
            LEFT JOIN poll_questions q ON q.poll_id = p.id
            WHERE q.id IS NULL
        """)
        legacy_polls = cur.fetchall()
        for poll in legacy_polls:
            poll_id, question = poll[0], poll[1]
            cur.execute(
                f"INSERT INTO poll_questions (poll_id, question_text, question_order) VALUES ({ph(3)})",
                (poll_id, question, 1),
            )
            cur.execute("SELECT MAX(id) FROM poll_questions")
            question_id = cur.fetchone()[0]
            cur.execute(
                f"UPDATE poll_options SET question_id = {ph()} WHERE poll_id = {ph()} AND question_id IS NULL",
                (question_id, poll_id),
            )
            cur.execute(
                f"UPDATE poll_votes SET question_id = {ph()} WHERE poll_id = {ph()} AND question_id IS NULL",
                (question_id, poll_id),
            )

        # ── High Scores ────────────────────────────────────────
        cur.execute("""
            SELECT DISTINCT v.poll_id, v.user_id
            FROM poll_votes v
            LEFT JOIN poll_submissions s ON s.poll_id = v.poll_id AND s.user_id = v.user_id
            WHERE s.id IS NULL
        """)
        legacy_submissions = cur.fetchall()
        for submission in legacy_submissions:
            cur.execute(
                f"INSERT INTO poll_submissions (poll_id, user_id) VALUES ({ph(2)})",
                (submission[0], submission[1]),
            )

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

        # Party Games rooms and players.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS party_rooms (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                code         TEXT    NOT NULL UNIQUE,
                game_key     TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'lobby',
                host_token   TEXT    NOT NULL,
                state_json   TEXT    NOT NULL DEFAULT '{}',
                created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS party_rooms (
                id           SERIAL PRIMARY KEY,
                code         TEXT    NOT NULL UNIQUE,
                game_key     TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'lobby',
                host_token   TEXT    NOT NULL,
                state_json   TEXT    NOT NULL DEFAULT '{}',
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS party_players (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id      INTEGER NOT NULL REFERENCES party_rooms(id) ON DELETE CASCADE,
                name         TEXT    NOT NULL,
                token        TEXT    NOT NULL,
                is_ready     INTEGER NOT NULL DEFAULT 0,
                score        INTEGER NOT NULL DEFAULT 0,
                joined_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                last_seen_at TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(room_id, token)
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS party_players (
                id           SERIAL PRIMARY KEY,
                room_id      INTEGER NOT NULL REFERENCES party_rooms(id) ON DELETE CASCADE,
                name         TEXT    NOT NULL,
                token        TEXT    NOT NULL,
                is_ready     BOOLEAN NOT NULL DEFAULT FALSE,
                score        INTEGER NOT NULL DEFAULT 0,
                joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(room_id, token)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_party_players_room ON party_players(room_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS party_scene_answers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id       INTEGER NOT NULL REFERENCES party_rooms(id) ON DELETE CASCADE,
                round_number  INTEGER NOT NULL,
                player_id     INTEGER NOT NULL REFERENCES party_players(id) ON DELETE CASCADE,
                answer_kind   TEXT    NOT NULL DEFAULT 'text',
                answer_text   TEXT    NOT NULL DEFAULT '',
                answer_image  TEXT    NOT NULL DEFAULT '',
                submitted_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(room_id, round_number, player_id)
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS party_scene_answers (
                id            SERIAL PRIMARY KEY,
                room_id       INTEGER NOT NULL REFERENCES party_rooms(id) ON DELETE CASCADE,
                round_number  INTEGER NOT NULL,
                player_id     INTEGER NOT NULL REFERENCES party_players(id) ON DELETE CASCADE,
                answer_kind   TEXT    NOT NULL DEFAULT 'text',
                answer_text   TEXT    NOT NULL DEFAULT '',
                answer_image  TEXT    NOT NULL DEFAULT '',
                submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(room_id, round_number, player_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_party_scene_answers_room_round ON party_scene_answers(room_id, round_number)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS party_scene_votes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id          INTEGER NOT NULL REFERENCES party_rooms(id) ON DELETE CASCADE,
                round_number     INTEGER NOT NULL,
                voter_player_id  INTEGER NOT NULL REFERENCES party_players(id) ON DELETE CASCADE,
                answer_player_id INTEGER NOT NULL REFERENCES party_players(id) ON DELETE CASCADE,
                voted_at         TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(room_id, round_number, voter_player_id)
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS party_scene_votes (
                id               SERIAL PRIMARY KEY,
                room_id          INTEGER NOT NULL REFERENCES party_rooms(id) ON DELETE CASCADE,
                round_number     INTEGER NOT NULL,
                voter_player_id  INTEGER NOT NULL REFERENCES party_players(id) ON DELETE CASCADE,
                answer_player_id INTEGER NOT NULL REFERENCES party_players(id) ON DELETE CASCADE,
                voted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(room_id, round_number, voter_player_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_party_scene_votes_room_round ON party_scene_votes(room_id, round_number)")

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

        # Shop orders and paid Pulse question submissions.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shop_orders (
                id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                product_key                TEXT    NOT NULL,
                status                     TEXT    NOT NULL DEFAULT 'pending',
                stripe_checkout_session_id TEXT    NOT NULL DEFAULT '',
                stripe_payment_intent_id   TEXT    NOT NULL DEFAULT '',
                amount_cents               INTEGER NOT NULL DEFAULT 0,
                currency                   TEXT    NOT NULL DEFAULT 'cad',
                customer_email             TEXT    NOT NULL DEFAULT '',
                question                   TEXT    NOT NULL DEFAULT '',
                option_a                   TEXT    NOT NULL DEFAULT '',
                option_b                   TEXT    NOT NULL DEFAULT '',
                option_c                   TEXT    NOT NULL DEFAULT '',
                option_d                   TEXT    NOT NULL DEFAULT '',
                display_name               TEXT    NOT NULL DEFAULT '',
                anonymous                  INTEGER NOT NULL DEFAULT 0,
                notes                      TEXT    NOT NULL DEFAULT '',
                created_at                 TEXT    NOT NULL DEFAULT (datetime('now')),
                paid_at                    TEXT,
                customer_email_sent_at     TEXT,
                admin_email_sent_at        TEXT
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS shop_orders (
                id                         SERIAL PRIMARY KEY,
                user_id                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                product_key                TEXT    NOT NULL,
                status                     TEXT    NOT NULL DEFAULT 'pending',
                stripe_checkout_session_id TEXT    NOT NULL DEFAULT '',
                stripe_payment_intent_id   TEXT    NOT NULL DEFAULT '',
                amount_cents               INTEGER NOT NULL DEFAULT 0,
                currency                   TEXT    NOT NULL DEFAULT 'cad',
                customer_email             TEXT    NOT NULL DEFAULT '',
                question                   TEXT    NOT NULL DEFAULT '',
                option_a                   TEXT    NOT NULL DEFAULT '',
                option_b                   TEXT    NOT NULL DEFAULT '',
                option_c                   TEXT    NOT NULL DEFAULT '',
                option_d                   TEXT    NOT NULL DEFAULT '',
                display_name               TEXT    NOT NULL DEFAULT '',
                anonymous                  BOOLEAN NOT NULL DEFAULT FALSE,
                notes                      TEXT    NOT NULL DEFAULT '',
                created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
                paid_at                    TIMESTAMPTZ,
                customer_email_sent_at     TIMESTAMPTZ,
                admin_email_sent_at        TIMESTAMPTZ
            )
        """)
        sent_at_definition = "TIMESTAMPTZ" if (_pg and DATABASE_URL) else "TEXT"
        _ensure_column(cur, "shop_orders", "customer_email_sent_at", sent_at_definition)
        _ensure_column(cur, "shop_orders", "admin_email_sent_at", sent_at_definition)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_shop_orders_status ON shop_orders(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_shop_orders_checkout_session ON shop_orders(stripe_checkout_session_id)")

        # Stripe-backed monthly support subscriptions.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_subscriptions (
                id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                tier                       TEXT    NOT NULL DEFAULT '',
                status                     TEXT    NOT NULL DEFAULT '',
                customer_email             TEXT    NOT NULL DEFAULT '',
                customer_name              TEXT    NOT NULL DEFAULT '',
                stripe_customer_id         TEXT    NOT NULL DEFAULT '',
                stripe_subscription_id     TEXT    NOT NULL UNIQUE,
                stripe_checkout_session_id TEXT    NOT NULL DEFAULT '',
                stripe_price_id            TEXT    NOT NULL DEFAULT '',
                amount_cents               INTEGER NOT NULL DEFAULT 0,
                currency                   TEXT    NOT NULL DEFAULT 'cad',
                current_period_start       TEXT,
                current_period_end         TEXT,
                cancel_at_period_end       INTEGER NOT NULL DEFAULT 0,
                canceled_at                TEXT,
                created_at                 TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at                 TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS support_subscriptions (
                id                         SERIAL PRIMARY KEY,
                user_id                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                tier                       TEXT    NOT NULL DEFAULT '',
                status                     TEXT    NOT NULL DEFAULT '',
                customer_email             TEXT    NOT NULL DEFAULT '',
                customer_name              TEXT    NOT NULL DEFAULT '',
                stripe_customer_id         TEXT    NOT NULL DEFAULT '',
                stripe_subscription_id     TEXT    NOT NULL UNIQUE,
                stripe_checkout_session_id TEXT    NOT NULL DEFAULT '',
                stripe_price_id            TEXT    NOT NULL DEFAULT '',
                amount_cents               INTEGER NOT NULL DEFAULT 0,
                currency                   TEXT    NOT NULL DEFAULT 'cad',
                current_period_start       TIMESTAMPTZ,
                current_period_end         TIMESTAMPTZ,
                cancel_at_period_end       BOOLEAN NOT NULL DEFAULT FALSE,
                canceled_at                TIMESTAMPTZ,
                created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_subscriptions_status ON support_subscriptions(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_subscriptions_tier ON support_subscriptions(tier)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_subscriptions_user ON support_subscriptions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_subscriptions_customer ON support_subscriptions(stripe_customer_id)")
        support_sent_at_definition = "TIMESTAMPTZ" if (_pg and DATABASE_URL) else "TEXT"
        _ensure_column(cur, "support_subscriptions", "admin_email_sent_at", support_sent_at_definition)

        # Stripe-backed one-time support payments.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_payments (
                id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                product_key                TEXT    NOT NULL DEFAULT '',
                support_slug               TEXT    NOT NULL DEFAULT '',
                customer_email             TEXT    NOT NULL DEFAULT '',
                customer_name              TEXT    NOT NULL DEFAULT '',
                stripe_customer_id         TEXT    NOT NULL DEFAULT '',
                stripe_checkout_session_id TEXT    NOT NULL UNIQUE,
                stripe_payment_intent_id   TEXT    NOT NULL DEFAULT '',
                stripe_price_id            TEXT    NOT NULL DEFAULT '',
                amount_cents               INTEGER NOT NULL DEFAULT 0,
                currency                   TEXT    NOT NULL DEFAULT 'cad',
                status                     TEXT    NOT NULL DEFAULT '',
                paid_at                    TEXT,
                admin_email_sent_at        TEXT,
                created_at                 TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at                 TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """) if not (_pg and DATABASE_URL) else cur.execute("""
            CREATE TABLE IF NOT EXISTS support_payments (
                id                         SERIAL PRIMARY KEY,
                user_id                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                product_key                TEXT    NOT NULL DEFAULT '',
                support_slug               TEXT    NOT NULL DEFAULT '',
                customer_email             TEXT    NOT NULL DEFAULT '',
                customer_name              TEXT    NOT NULL DEFAULT '',
                stripe_customer_id         TEXT    NOT NULL DEFAULT '',
                stripe_checkout_session_id TEXT    NOT NULL UNIQUE,
                stripe_payment_intent_id   TEXT    NOT NULL DEFAULT '',
                stripe_price_id            TEXT    NOT NULL DEFAULT '',
                amount_cents               INTEGER NOT NULL DEFAULT 0,
                currency                   TEXT    NOT NULL DEFAULT 'cad',
                status                     TEXT    NOT NULL DEFAULT '',
                paid_at                    TIMESTAMPTZ,
                admin_email_sent_at        TIMESTAMPTZ,
                created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_payments_customer ON support_payments(customer_email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_payments_session ON support_payments(stripe_checkout_session_id)")

        conn.commit()
