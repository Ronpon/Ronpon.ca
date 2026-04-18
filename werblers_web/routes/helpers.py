"""Shared helpers for all route blueprints.

Keeps session management, state-building wrappers, and enrichment helpers
in one place so blueprints don't import directly from app.py.
"""
from __future__ import annotations

from flask import session

from werblers_web.serializers import (
    enrich_combat_info as _enrich_combat_info_impl,
    build_state as _build_state_impl,
)

# Per-session game state: session_id -> {"game": Game, "last_log": list, "pending_log": list}
_sessions: dict[str, dict] = {}


def _get_state() -> dict:
    """Return the mutable state dict for the current browser session.

    Returns a dummy empty state if no game session exists yet (so callers
    can safely check state["game"] is None without crashing).
    """
    sid = session.get("game_id")
    if not sid or sid not in _sessions:
        return {"game": None, "last_log": [], "pending_log": []}
    return _sessions[sid]


def _enrich_combat_info(info: dict) -> dict:
    """Thin wrapper that passes game context to serializers.enrich_combat_info."""
    return _enrich_combat_info_impl(info, _get_state()["game"], _get_state)


def _build_state() -> dict:
    """Thin wrapper that passes session getter to serializers.build_state."""
    return _build_state_impl(_get_state)
