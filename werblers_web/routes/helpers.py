"""Shared helpers for all route blueprints.

Keeps session management, state-building wrappers, and enrichment helpers
in one place so blueprints don't import directly from app.py.
"""
from __future__ import annotations

import os
import time
import uuid

from flask import session, request, jsonify, g

from werblers_web.serializers import (
    enrich_combat_info as _enrich_combat_info_impl,
    build_state as _build_state_impl,
)

# Per-session game state: session_id -> {"game": Game, "last_log": list, "pending_log": list}
_sessions: dict[str, dict] = {}
_SESSION_TTL_SECONDS = int(os.environ.get("WERBLERS_SESSION_TTL_SECONDS", str(24 * 60 * 60)))
_MAX_ACTIVE_SESSIONS = int(os.environ.get("WERBLERS_MAX_ACTIVE_SESSIONS", "500"))


def _cleanup_sessions(now: float | None = None) -> None:
    now = now or time.time()
    expired = [
        sid for sid, state in _sessions.items()
        if now - float(state.get("last_seen", state.get("created_at", now))) > _SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)

    overflow = len(_sessions) - _MAX_ACTIVE_SESSIONS
    if overflow > 0:
        oldest = sorted(
            _sessions,
            key=lambda sid: float(_sessions[sid].get("last_seen", _sessions[sid].get("created_at", now))),
        )
        for sid in oldest[:overflow]:
            _sessions.pop(sid, None)


def _set_game_state(game, initial_log: list[str] | None = None) -> str:
    now = time.time()
    previous_sid = session.get("game_id")
    if previous_sid:
        _sessions.pop(previous_sid, None)
    _cleanup_sessions(now)
    sid = str(uuid.uuid4())
    session["game_id"] = sid
    _sessions[sid] = {
        "game": game,
        "last_log": initial_log or [],
        "pending_log": [],
        "created_at": now,
        "last_seen": now,
    }
    return sid


def _get_state() -> dict:
    """Return the mutable state dict for the current browser session.

    Returns a dummy empty state if no game session exists yet (so callers
    can safely check state["game"] is None without crashing).
    """
    if hasattr(g, "werblers_room_state"):
        return g.werblers_room_state
    sid = session.get("game_id")
    if not sid or sid not in _sessions:
        return {"game": None, "last_log": [], "pending_log": []}
    state = _sessions[sid]
    now = time.time()
    if now - float(state.get("last_seen", state.get("created_at", now))) > _SESSION_TTL_SECONDS:
        _sessions.pop(sid, None)
        session.pop("game_id", None)
        return {"game": None, "last_log": [], "pending_log": []}
    state["last_seen"] = now
    return state


def _enrich_combat_info(info: dict) -> dict:
    """Thin wrapper that passes game context to serializers.enrich_combat_info."""
    return _enrich_combat_info_impl(info, _get_state()["game"], _get_state)


def _build_state() -> dict:
    """Thin wrapper that passes session getter to serializers.build_state."""
    return _build_state_impl(_get_state)


def require_me_too_resolved():
    """Keep actions from invalidating an outstanding loss or reaction choice."""
    if request.method != "POST" or request.endpoint == "game.api_new_game":
        return None
    game = _get_state()["game"]
    if game is None:
        return None
    if game._pending_trait_loss is not None and request.endpoint != "game.api_resolve_trait_loss":
        return jsonify({"error": "Choose the traits to lose first.", "state": _build_state()}), 409
    if game.pending_me_too() is not None and request.endpoint != "game.api_resolve_me_too":
        return jsonify({"error": "Resolve Me Too! first.", "state": _build_state()}), 409


def action_body():
    """Room actions use the same handlers and rules as local games."""
    if hasattr(g, "werblers_action_body"):
        return g.werblers_action_body
    from security import json_body
    return json_body()
