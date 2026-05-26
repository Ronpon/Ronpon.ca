"""Room and player persistence for Party Games."""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from models.db import get_conn, ph


MAX_PLAYERS_PER_ROOM = 12
MAX_PLAYER_NAME_LENGTH = 24
ROOM_CODE_LENGTH = 4
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_TTL_HOURS = 12


class PartyGameError(ValueError):
    """Raised when a room action is invalid for the current state."""


def normalize_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())[:ROOM_CODE_LENGTH]


def clean_player_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    return cleaned[:MAX_PLAYER_NAME_LENGTH]


def new_token() -> str:
    return secrets.token_urlsafe(24)


def cleanup_expired_rooms(hours: int = ROOM_TTL_HOURS) -> int:
    cutoff = _stamp(datetime.now(timezone.utc) - timedelta(hours=hours))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id FROM party_rooms WHERE updated_at < {ph()}", (cutoff,))
        room_ids = [row[0] for row in cur.fetchall()]
        if not room_ids:
            return 0
        placeholders = ph(len(room_ids))
        cur.execute(f"DELETE FROM party_players WHERE room_id IN ({placeholders})", tuple(room_ids))
        cur.execute(f"DELETE FROM party_rooms WHERE id IN ({placeholders})", tuple(room_ids))
        return len(room_ids)


def create_room(game_key: str, host_token: str) -> dict[str, Any]:
    cleanup_expired_rooms()
    with get_conn() as conn:
        cur = conn.cursor()
        for _ in range(40):
            code = _make_room_code()
            cur.execute(f"SELECT 1 FROM party_rooms WHERE code = {ph()}", (code,))
            if cur.fetchone():
                continue
            now = _stamp()
            cur.execute(
                f"""
                INSERT INTO party_rooms
                    (code, game_key, status, host_token, state_json, created_at, updated_at)
                VALUES ({ph(7)})
                """,
                (code, game_key, "lobby", host_token, json.dumps({"round": 0}), now, now),
            )
            return _select_room_by_code(cur, code)
    raise PartyGameError("Could not create a room code. Please try again.")


def get_room(code: str) -> dict[str, Any] | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        return _select_room_by_code(cur, normalized)


def join_room(code: str, player_token: str, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = normalize_code(code)
    player_name = clean_player_name(name)
    if not normalized:
        raise PartyGameError("Enter a room code.")
    if not player_name:
        raise PartyGameError("Enter a display name.")

    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room_by_code(cur, normalized)
        if not room or room["status"] == "closed":
            raise PartyGameError("That room was not found.")

        existing = _select_player_by_token(cur, room["id"], player_token)
        if existing:
            now = _stamp()
            cur.execute(
                f"""
                UPDATE party_players
                SET name = {ph()}, last_seen_at = {ph()}
                WHERE room_id = {ph()} AND token = {ph()}
                """,
                (player_name, now, room["id"], player_token),
            )
            _touch_room(cur, room["id"], now)
            return room, _select_player_by_token(cur, room["id"], player_token)

        if room["status"] != "lobby":
            raise PartyGameError("That game has already started.")

        cur.execute(f"SELECT COUNT(*) FROM party_players WHERE room_id = {ph()}", (room["id"],))
        if cur.fetchone()[0] >= MAX_PLAYERS_PER_ROOM:
            raise PartyGameError("That room is full.")

        now = _stamp()
        cur.execute(
            f"""
            INSERT INTO party_players
                (room_id, name, token, is_ready, score, joined_at, last_seen_at)
            VALUES ({ph(7)})
            """,
            (room["id"], player_name, player_token, 0, 0, now, now),
        )
        _touch_room(cur, room["id"], now)
        return room, _select_player_by_token(cur, room["id"], player_token)


def snapshot_room(
    code: str,
    *,
    host_token: str | None = None,
    player_token: str | None = None,
) -> dict[str, Any] | None:
    normalized = normalize_code(code)
    if not normalized:
        return None

    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room_by_code(cur, normalized)
        if not room:
            return None

        now = _stamp()
        is_host = bool(host_token and secrets.compare_digest(host_token, room["host_token"]))
        player = None
        if player_token:
            player = _select_player_by_token(cur, room["id"], player_token)

        if is_host:
            _touch_room(cur, room["id"], now)
        if player:
            cur.execute(
                f"UPDATE party_players SET last_seen_at = {ph()} WHERE id = {ph()}",
                (now, player["id"]),
            )
            _touch_room(cur, room["id"], now)
            player = _select_player_by_token(cur, room["id"], player_token)

        players = _select_players(cur, room["id"])
        room["player_count"] = len(players)
        return {
            "room": _public_room(room),
            "players": [_public_player(p) for p in players],
            "current_player": _public_player(player) if player else None,
            "is_host": is_host,
            "server_time": now,
        }


def set_player_ready(code: str, player_token: str, is_ready: bool) -> dict[str, Any] | None:
    normalized = normalize_code(code)
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room_by_code(cur, normalized)
        if not room:
            return None
        player = _select_player_by_token(cur, room["id"], player_token)
        if not player:
            return None
        now = _stamp()
        cur.execute(
            f"""
            UPDATE party_players
            SET is_ready = {ph()}, last_seen_at = {ph()}
            WHERE id = {ph()}
            """,
            (1 if is_ready else 0, now, player["id"]),
        )
        _touch_room(cur, room["id"], now)
        return _select_player_by_token(cur, room["id"], player_token)


def leave_room(code: str, player_token: str) -> bool:
    normalized = normalize_code(code)
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room_by_code(cur, normalized)
        if not room:
            return False
        cur.execute(
            f"DELETE FROM party_players WHERE room_id = {ph()} AND token = {ph()}",
            (room["id"], player_token),
        )
        _touch_room(cur, room["id"])
        return True


def set_room_status(code: str, host_token: str, status: str) -> dict[str, Any] | None:
    if status not in {"lobby", "playing", "closed"}:
        raise PartyGameError("Unsupported room status.")
    normalized = normalize_code(code)
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room_by_code(cur, normalized)
        if not _host_matches(room, host_token):
            return None

        now = _stamp()
        if status == "lobby":
            cur.execute(
                f"UPDATE party_players SET is_ready = {ph()} WHERE room_id = {ph()}",
                (0, room["id"]),
            )
        cur.execute(
            f"UPDATE party_rooms SET status = {ph()}, updated_at = {ph()} WHERE id = {ph()}",
            (status, now, room["id"]),
        )
        return _select_room_by_code(cur, normalized)


def reset_room(code: str, host_token: str) -> dict[str, Any] | None:
    normalized = normalize_code(code)
    with get_conn() as conn:
        cur = conn.cursor()
        room = _select_room_by_code(cur, normalized)
        if not _host_matches(room, host_token):
            return None

        now = _stamp()
        cur.execute(
            f"""
            UPDATE party_rooms
            SET status = {ph()}, state_json = {ph()}, updated_at = {ph()}
            WHERE id = {ph()}
            """,
            ("lobby", json.dumps({"round": 0}), now, room["id"]),
        )
        cur.execute(
            f"UPDATE party_players SET is_ready = {ph()}, score = {ph()} WHERE room_id = {ph()}",
            (0, 0, room["id"]),
        )
        return _select_room_by_code(cur, normalized)


def host_can_manage(code: str, host_token: str | None) -> bool:
    room = get_room(code)
    return _host_matches(room, host_token)


def _make_room_code() -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def _select_room_by_code(cur, code: str) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT id, code, game_key, status, host_token, state_json, created_at, updated_at
        FROM party_rooms
        WHERE code = {ph()}
        """,
        (code,),
    )
    row = cur.fetchone()
    return _room_from_row(row) if row else None


def _select_player_by_token(cur, room_id: int, token: str) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT id, room_id, name, token, is_ready, score, joined_at, last_seen_at
        FROM party_players
        WHERE room_id = {ph()} AND token = {ph()}
        """,
        (room_id, token),
    )
    row = cur.fetchone()
    return _player_from_row(row) if row else None


def _select_players(cur, room_id: int) -> list[dict[str, Any]]:
    cur.execute(
        f"""
        SELECT id, room_id, name, token, is_ready, score, joined_at, last_seen_at
        FROM party_players
        WHERE room_id = {ph()}
        ORDER BY joined_at, id
        """,
        (room_id,),
    )
    return [_player_from_row(row) for row in cur.fetchall()]


def _touch_room(cur, room_id: int, now: str | None = None) -> None:
    cur.execute(
        f"UPDATE party_rooms SET updated_at = {ph()} WHERE id = {ph()}",
        (now or _stamp(), room_id),
    )


def _host_matches(room: dict[str, Any] | None, host_token: str | None) -> bool:
    return bool(room and host_token and secrets.compare_digest(host_token, room["host_token"]))


def _room_from_row(row) -> dict[str, Any]:
    raw_state = _field(row, "state_json", 5) or "{}"
    try:
        state = json.loads(raw_state)
    except (TypeError, json.JSONDecodeError):
        state = {}
    return {
        "id": _field(row, "id", 0),
        "code": _field(row, "code", 1),
        "game_key": _field(row, "game_key", 2),
        "status": _field(row, "status", 3),
        "host_token": _field(row, "host_token", 4),
        "state": state,
        "created_at": _field(row, "created_at", 6),
        "updated_at": _field(row, "updated_at", 7),
    }


def _player_from_row(row) -> dict[str, Any]:
    return {
        "id": _field(row, "id", 0),
        "room_id": _field(row, "room_id", 1),
        "name": _field(row, "name", 2),
        "token": _field(row, "token", 3),
        "is_ready": bool(_field(row, "is_ready", 4)),
        "score": int(_field(row, "score", 5) or 0),
        "joined_at": _field(row, "joined_at", 6),
        "last_seen_at": _field(row, "last_seen_at", 7),
    }


def _public_room(room: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": room["code"],
        "game_key": room["game_key"],
        "status": room["status"],
        "state": room["state"],
        "player_count": room.get("player_count", 0),
    }


def _public_player(player: dict[str, Any] | None) -> dict[str, Any] | None:
    if not player:
        return None
    return {
        "id": player["id"],
        "name": player["name"],
        "is_ready": player["is_ready"],
        "score": player["score"],
        "is_connected": _is_recent(player["last_seen_at"]),
    }


def _is_recent(value: Any) -> bool:
    seen_at = _parse_datetime(value)
    if not seen_at:
        return False
    return datetime.now(timezone.utc).replace(tzinfo=None) - seen_at <= timedelta(seconds=45)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _stamp(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _field(row, key: str, index: int):
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]
