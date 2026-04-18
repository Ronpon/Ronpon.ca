"""Database module for Werblers — profiles, saves, achievements.

Uses PostgreSQL via psycopg2.  Falls back to SQLite for local dev when
the DATABASE_URL env var is not set.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")

# psycopg2 is optional — only needed when DATABASE_URL is set
_pg = None
if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        _pg = psycopg2
    except ImportError:
        pass

_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "werblers_local.db",
)


@contextmanager
def _get_conn():
    """Yield a DB-API 2.0 connection (PostgreSQL or SQLite)."""
    if _pg and DATABASE_URL:
        conn = _pg.connect(DATABASE_URL, sslmode="require")
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


def _ph(n: int = 1) -> str:
    """Return placeholder(s) for the active DB backend (%s or ?)."""
    p = "%s" if (_pg and DATABASE_URL) else "?"
    return ", ".join([p] * n)


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS profiles (
    id          SERIAL PRIMARY KEY,
    device_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS saves (
    id            SERIAL PRIMARY KEY,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    slot_number   INTEGER NOT NULL,
    game_state    TEXT NOT NULL,
    turn_number   INTEGER NOT NULL DEFAULT 0,
    num_players   INTEGER NOT NULL DEFAULT 1,
    hero_names    TEXT NOT NULL DEFAULT '',
    saved_at      TEXT NOT NULL DEFAULT '',
    UNIQUE(profile_id, slot_number)
);

CREATE TABLE IF NOT EXISTS achievements (
    id            SERIAL PRIMARY KEY,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    achievement   TEXT NOT NULL,
    achieved_at   TEXT NOT NULL DEFAULT '',
    UNIQUE(profile_id, achievement)
);
"""

# SQLite uses AUTOINCREMENT differently — use a compatible variant
_SCHEMA_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS profiles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS saves (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    slot_number   INTEGER NOT NULL,
    game_state    TEXT NOT NULL,
    turn_number   INTEGER NOT NULL DEFAULT 0,
    num_players   INTEGER NOT NULL DEFAULT 1,
    hero_names    TEXT NOT NULL DEFAULT '',
    saved_at      TEXT NOT NULL DEFAULT '',
    UNIQUE(profile_id, slot_number)
);

CREATE TABLE IF NOT EXISTS achievements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id    INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    achievement   TEXT NOT NULL,
    achieved_at   TEXT NOT NULL DEFAULT '',
    UNIQUE(profile_id, achievement)
);
"""


def init_db() -> None:
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        cur = conn.cursor()
        if _pg and DATABASE_URL:
            cur.execute(_SCHEMA_SQL)
        else:
            cur.executescript(_SCHEMA_SQL_SQLITE)


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

def create_profile(device_id: str, name: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        cur = conn.cursor()
        if _pg and DATABASE_URL:
            cur.execute(
                f"INSERT INTO profiles (device_id, name, created_at) VALUES ({_ph(3)}) RETURNING id",
                (device_id, name, now),
            )
            pid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO profiles (device_id, name, created_at) VALUES ({_ph(3)})",
                (device_id, name, now),
            )
            pid = cur.lastrowid
    return {"id": pid, "device_id": device_id, "name": name, "created_at": now}


def list_profiles(device_id: str) -> list[dict]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, device_id, name, created_at FROM profiles WHERE device_id = {_ph()} ORDER BY id",
            (device_id,),
        )
        rows = cur.fetchall()
    return [{"id": r[0], "device_id": r[1], "name": r[2], "created_at": r[3]} for r in rows]


def get_profile(profile_id: int) -> Optional[dict]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, device_id, name, created_at FROM profiles WHERE id = {_ph()}",
            (profile_id,),
        )
        r = cur.fetchone()
    if r is None:
        return None
    return {"id": r[0], "device_id": r[1], "name": r[2], "created_at": r[3]}


# ---------------------------------------------------------------------------
# Save CRUD
# ---------------------------------------------------------------------------

def save_game(profile_id: int, slot_number: int, game_state_json: str,
              turn_number: int, num_players: int, hero_names: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        cur = conn.cursor()
        if _pg and DATABASE_URL:
            cur.execute(
                f"""INSERT INTO saves (profile_id, slot_number, game_state, turn_number, num_players, hero_names, saved_at)
                    VALUES ({_ph(7)})
                    ON CONFLICT (profile_id, slot_number)
                    DO UPDATE SET game_state = EXCLUDED.game_state,
                                  turn_number = EXCLUDED.turn_number,
                                  num_players = EXCLUDED.num_players,
                                  hero_names = EXCLUDED.hero_names,
                                  saved_at = EXCLUDED.saved_at
                    RETURNING id""",
                (profile_id, slot_number, game_state_json, turn_number, num_players, hero_names, now),
            )
            sid = cur.fetchone()[0]
        else:
            cur.execute(
                f"""INSERT OR REPLACE INTO saves (profile_id, slot_number, game_state, turn_number, num_players, hero_names, saved_at)
                    VALUES ({_ph(7)})""",
                (profile_id, slot_number, game_state_json, turn_number, num_players, hero_names, now),
            )
            sid = cur.lastrowid
    return {"id": sid, "slot_number": slot_number, "saved_at": now}


def list_saves(profile_id: int) -> list[dict]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT id, slot_number, turn_number, num_players, hero_names, saved_at
                FROM saves WHERE profile_id = {_ph()} ORDER BY slot_number""",
            (profile_id,),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "slot_number": r[1], "turn_number": r[2],
         "num_players": r[3], "hero_names": r[4], "saved_at": r[5]}
        for r in rows
    ]


def load_save(profile_id: int, slot_number: int) -> Optional[str]:
    """Return the raw game_state JSON string, or None."""
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT game_state FROM saves WHERE profile_id = {_ph()} AND slot_number = {_ph()}",
            (profile_id, slot_number),
        )
        row = cur.fetchone()
    return row[0] if row else None


def delete_save(profile_id: int, slot_number: int) -> bool:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM saves WHERE profile_id = {_ph()} AND slot_number = {_ph()}",
            (profile_id, slot_number),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Achievement CRUD
# ---------------------------------------------------------------------------

ACHIEVEMENT_DEFS = {
    "a_strong_start":       "A Strong Start: Defeat the first Miniboss.",
    "getting_closer":       "Getting Closer: Defeat the second Miniboss.",
    "victory":              "Victory: Defeat the Werbler once.",
    "this_is_easy":         "This is Easy: Defeat the Werbler 5 times.",
    "champion":             "Champion: Win 1 multiplayer game.",
    "stop_beating_your_wife": "Stop Beating Your Wife: Win 5 multiplayer games.",
    "total_victory":        "Total Victory: Complete all the achievements.",
}


def grant_achievement(profile_id: int, achievement_key: str) -> bool:
    """Grant an achievement.  Returns True if newly granted, False if already had."""
    if achievement_key not in ACHIEVEMENT_DEFS:
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                f"INSERT INTO achievements (profile_id, achievement, achieved_at) VALUES ({_ph(3)})",
                (profile_id, achievement_key, now),
            )
            return True
        except Exception:
            # Already exists (unique constraint)
            return False


def list_achievements(profile_id: int) -> list[dict]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT achievement, achieved_at FROM achievements WHERE profile_id = {_ph()} ORDER BY achieved_at",
            (profile_id,),
        )
        rows = cur.fetchall()
    earned = {r[0]: r[1] for r in rows}
    result = []
    for key, desc in ACHIEVEMENT_DEFS.items():
        result.append({
            "key": key,
            "description": desc,
            "achieved": key in earned,
            "achieved_at": earned.get(key, None),
        })
    return result


def count_achievements(profile_id: int) -> int:
    """Count how many achievements (excluding total_victory) the profile has."""
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM achievements WHERE profile_id = {_ph()} AND achievement != 'total_victory'",
            (profile_id,),
        )
        return cur.fetchone()[0]


def count_werbler_wins(profile_id: int) -> int:
    """Count how many times the Werbler has been defeated (from achievements tracking table)."""
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM achievements WHERE profile_id = {_ph()} AND achievement = 'victory'",
            (profile_id,),
        )
        return cur.fetchone()[0]
