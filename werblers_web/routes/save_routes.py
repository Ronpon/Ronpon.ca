"""Profile, save/load, and achievement API routes."""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request, session
from flask_login import current_user

from werblers_engine import database as db
from werblers_engine.save_load import serialize_game, deserialize_game
from werblers_web.routes.helpers import _sessions, _get_state, _build_state

save_bp = Blueprint("save", __name__)


def _profile_token_from_request(data: dict | None = None) -> str:
    if data and data.get("profile_token"):
        return str(data.get("profile_token", ""))
    return request.args.get("profile_token", "")


def _authorized_profile(profile_id: int, data: dict | None = None) -> bool:
    if current_user.is_authenticated and db.profile_belongs_to_user(profile_id, current_user.id):
        return True
    return db.profile_token_matches(profile_id, _profile_token_from_request(data))


@save_bp.route("/api/profiles", methods=["GET"])
def api_list_profiles():
    device_id = request.args.get("device_id", "")
    if current_user.is_authenticated:
        return jsonify({"profiles": db.list_profiles(user_id=current_user.id)})
    if not device_id:
        return jsonify({"error": "device_id required"}), 400
    return jsonify({"profiles": db.list_profiles(device_id)})

@save_bp.route("/api/profiles", methods=["POST"])
def api_create_profile():
    data = request.get_json(force=True) or {}
    device_id = data.get("device_id", "")
    name = data.get("name", "").strip()
    if not device_id or not name:
        return jsonify({"error": "device_id and name required"}), 400
    if not device_id.startswith("dev_") or len(device_id) > 64:
        return jsonify({"error": "Invalid device_id"}), 400
    if len(name) > 24:
        return jsonify({"error": "Name is too long"}), 400
    user_id = current_user.id if current_user.is_authenticated else None
    profile = db.create_profile(device_id, name, user_id=user_id)
    return jsonify({"profile": profile})

@save_bp.route("/api/saves", methods=["GET"])
def api_list_saves():
    profile_id = request.args.get("profile_id", type=int)
    if profile_id is None:
        return jsonify({"error": "profile_id required"}), 400
    if not _authorized_profile(profile_id):
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"saves": db.list_saves(profile_id)})

@save_bp.route("/api/save", methods=["POST"])
def api_save_game():
    _game = _get_state()["game"]
    if _game is None:
        return jsonify({"error": "No game in progress"}), 400
    data = request.get_json(force=True) or {}
    profile_id = data.get("profile_id")
    slot_number = data.get("slot_number")
    if profile_id is None or slot_number is None:
        return jsonify({"error": "profile_id and slot_number required"}), 400
    if not _authorized_profile(int(profile_id), data):
        return jsonify({"error": "Profile not found"}), 404
    slot_number = int(slot_number)
    if not 1 <= slot_number <= 10:
        return jsonify({"error": "slot_number must be 1-10"}), 400
    game_json = serialize_game(_game)
    hero_names = ", ".join(p.name for p in _game.players)
    result = db.save_game(
        profile_id=int(profile_id),
        slot_number=slot_number,
        game_state_json=game_json,
        turn_number=_game.turn_number,
        num_players=len(_game.players),
        hero_names=hero_names,
    )
    return jsonify({"ok": True, "save": result})

@save_bp.route("/api/load", methods=["POST"])
def api_load_game():
    data = request.get_json(force=True) or {}
    profile_id = data.get("profile_id")
    slot_number = data.get("slot_number")
    if profile_id is None or slot_number is None:
        return jsonify({"error": "profile_id and slot_number required"}), 400
    if not _authorized_profile(int(profile_id), data):
        return jsonify({"error": "Save not found"}), 404
    game_json = db.load_save(int(profile_id), int(slot_number))
    if game_json is None:
        return jsonify({"error": "Save not found"}), 404
    game = deserialize_game(game_json)
    sid = str(uuid.uuid4())
    session["game_id"] = sid
    _sessions[sid] = {"game": game, "last_log": ["Game loaded!"], "pending_log": []}
    return jsonify({"ok": True, "state": _build_state()})

@save_bp.route("/api/achievements", methods=["GET"])
def api_list_achievements():
    profile_id = request.args.get("profile_id", type=int)
    if profile_id is None:
        return jsonify({"error": "profile_id required"}), 400
    if not _authorized_profile(profile_id):
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"achievements": db.list_achievements(profile_id)})

@save_bp.route("/api/achievements", methods=["POST"])
def api_grant_achievement():
    data = request.get_json(force=True) or {}
    profile_id = data.get("profile_id")
    achievement_key = data.get("achievement")
    if profile_id is None or not achievement_key:
        return jsonify({"error": "profile_id and achievement required"}), 400
    if not _authorized_profile(int(profile_id), data):
        return jsonify({"error": "Profile not found"}), 404
    newly = db.grant_achievement(int(profile_id), achievement_key)
    # Check for Total Victory
    if newly and achievement_key != "total_victory":
        non_total = len(db.ACHIEVEMENT_DEFS) - 1  # exclude total_victory itself
        earned = db.count_achievements(int(profile_id))
        if earned >= non_total:
            db.grant_achievement(int(profile_id), "total_victory")
    return jsonify({"ok": True, "newly_granted": newly,
                    "achievements": db.list_achievements(int(profile_id))})
