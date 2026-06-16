"""Party Games lobby and realtime-ish room routes."""
from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user

from models import party_games, scenes_phone
from security import rate_limit


party_games_bp = Blueprint("party_games", __name__)

PARTY_GAME_CATALOG = {
    "scenes-from-your-phone": {
        "key": "scenes-from-your-phone",
        "title": "Scenes From Your Phone",
        "description": "Write, jumble, or draw anonymous prompt answers, then vote for the funniest.",
        "player_range": "2-12",
    },
    "lobby-test": {
        "key": "lobby-test",
        "title": "Lobby Test",
        "description": "A reusable room-code lobby for the first wave of Party Games.",
        "player_range": "2-12",
    }
}

HOST_SESSION_KEY = "party_host_tokens"
PLAYER_SESSION_KEY = "party_player_tokens"


@party_games_bp.route("/")
def index():
    code = party_games.normalize_code(request.args.get("code", ""))
    default_name = ""
    if current_user.is_authenticated:
        default_name = party_games.clean_player_name(current_user.username)
    return render_template(
        "party_games/index.html",
        games=list(PARTY_GAME_CATALOG.values()),
        prefill_code=code,
        default_name=default_name,
        max_name_length=party_games.MAX_PLAYER_NAME_LENGTH,
    )


@party_games_bp.post("/rooms")
@rate_limit("party.create_room", 20, 60 * 60)
def create_room():
    game_key = request.form.get("game_key", "lobby-test")
    host_name = party_games.clean_player_name(request.form.get("host_name", ""))
    if game_key not in PARTY_GAME_CATALOG:
        flash("Choose a Party Game.", "error")
        return redirect(url_for("party_games.index"))
    if not host_name:
        flash("Enter your display name.", "error")
        return redirect(url_for("party_games.index"))

    host_token = party_games.new_token()
    try:
        room = party_games.create_room(game_key, host_token)
        party_games.join_room(room["code"], host_token, host_name)
    except party_games.PartyGameError as exc:
        flash(str(exc), "error")
        return redirect(url_for("party_games.index"))

    _store_session_token(HOST_SESSION_KEY, room["code"], host_token)
    _store_session_token(PLAYER_SESSION_KEY, room["code"], host_token)
    return redirect(url_for("party_games.host_room", code=room["code"]))


@party_games_bp.post("/join")
@rate_limit("party.join_room", 60, 10 * 60)
def join_room():
    code = party_games.normalize_code(request.form.get("code", ""))
    name = party_games.clean_player_name(request.form.get("name", ""))
    if not code:
        flash("Enter a room code.", "error")
        return redirect(url_for("party_games.index"))
    if not name:
        flash("Enter a display name.", "error")
        return redirect(url_for("party_games.index", code=code))

    player_token = _session_token(PLAYER_SESSION_KEY, code) or party_games.new_token()
    try:
        room, _player = party_games.join_room(code, player_token, name)
    except party_games.PartyGameError as exc:
        flash(str(exc), "error")
        return redirect(url_for("party_games.index", code=code))

    _store_session_token(PLAYER_SESSION_KEY, room["code"], player_token)
    return redirect(url_for("party_games.player_room", code=room["code"]))


@party_games_bp.get("/rooms/<code>/host")
def host_room(code):
    normalized = party_games.normalize_code(code)
    host_token = _session_token(HOST_SESSION_KEY, normalized)
    player_token = _session_token(PLAYER_SESSION_KEY, normalized)
    if host_token and not player_token:
        player_token = host_token
        _store_session_token(PLAYER_SESSION_KEY, normalized, player_token)
    snapshot = _snapshot(normalized, host_token=host_token, player_token=player_token)
    if not snapshot or not snapshot["is_host"]:
        flash("Host access for that room was not found in this browser.", "error")
        return redirect(url_for("party_games.index", code=normalized))

    return render_template(
        "party_games/host.html",
        game=_game_for_snapshot(snapshot),
        snapshot=snapshot,
        join_url=url_for("party_games.index", code=normalized, _external=True),
    )


@party_games_bp.get("/rooms/<code>/player")
def player_room(code):
    normalized = party_games.normalize_code(code)
    player_token = _session_token(PLAYER_SESSION_KEY, normalized)
    snapshot = _snapshot(normalized, player_token=player_token)
    if not snapshot or not snapshot["current_player"]:
        flash("Join that room to play.", "error")
        return redirect(url_for("party_games.index", code=normalized))

    return render_template(
        "party_games/player.html",
        game=_game_for_snapshot(snapshot),
        snapshot=snapshot,
        max_name_length=party_games.MAX_PLAYER_NAME_LENGTH,
    )


@party_games_bp.get("/api/rooms/<code>")
def room_state(code):
    normalized = party_games.normalize_code(code)
    snapshot = _snapshot(
        normalized,
        host_token=_session_token(HOST_SESSION_KEY, normalized),
        player_token=_session_token(PLAYER_SESSION_KEY, normalized),
    )
    if not snapshot:
        return jsonify({"error": "Room not found."}), 404
    return jsonify(snapshot)


@party_games_bp.post("/api/rooms/<code>/start")
@rate_limit("party.room_action", 120, 60)
def start_room(code):
    normalized = party_games.normalize_code(code)
    host_token = _session_token(HOST_SESSION_KEY, normalized)
    room = party_games.get_room(normalized)
    if room and room["game_key"] == scenes_phone.GAME_KEY:
        try:
            scenes_phone.start_game(normalized, host_token or "", request.get_json(silent=True) or {})
        except scenes_phone.ScenesError as exc:
            return jsonify({"error": str(exc)}), 400
        return _snapshot_json(
            normalized,
            host_token=host_token,
            player_token=_session_token(PLAYER_SESSION_KEY, normalized),
        )

    if not party_games.set_room_status(normalized, host_token or "", "playing"):
        return jsonify({"error": "Host access required."}), 403
    return _snapshot_json(
        normalized,
        host_token=host_token,
        player_token=_session_token(PLAYER_SESSION_KEY, normalized),
    )


@party_games_bp.post("/api/rooms/<code>/reset")
@rate_limit("party.room_action", 120, 60)
def reset_room(code):
    normalized = party_games.normalize_code(code)
    host_token = _session_token(HOST_SESSION_KEY, normalized)
    room = party_games.get_room(normalized)
    if room and room["game_key"] == scenes_phone.GAME_KEY:
        try:
            scenes_phone.reset_room(normalized, host_token or "")
        except scenes_phone.ScenesError as exc:
            return jsonify({"error": str(exc)}), 400
        return _snapshot_json(
            normalized,
            host_token=host_token,
            player_token=_session_token(PLAYER_SESSION_KEY, normalized),
        )

    if not party_games.reset_room(normalized, host_token or ""):
        return jsonify({"error": "Host access required."}), 403
    return _snapshot_json(
        normalized,
        host_token=host_token,
        player_token=_session_token(PLAYER_SESSION_KEY, normalized),
    )


@party_games_bp.post("/api/rooms/<code>/close")
@rate_limit("party.room_action", 120, 60)
def close_room(code):
    normalized = party_games.normalize_code(code)
    host_token = _session_token(HOST_SESSION_KEY, normalized)
    if not party_games.set_room_status(normalized, host_token or "", "closed"):
        return jsonify({"error": "Host access required."}), 403
    _remove_session_token(HOST_SESSION_KEY, normalized)
    _remove_session_token(PLAYER_SESSION_KEY, normalized)
    return jsonify({"ok": True, "redirect": url_for("party_games.index")})


@party_games_bp.post("/api/rooms/<code>/ready")
@rate_limit("party.room_action", 120, 60)
def set_ready(code):
    normalized = party_games.normalize_code(code)
    player_token = _session_token(PLAYER_SESSION_KEY, normalized)
    payload = request.get_json(silent=True) or {}
    player = party_games.set_player_ready(normalized, player_token or "", bool(payload.get("is_ready")))
    if not player:
        return jsonify({"error": "Player access required."}), 403
    return _snapshot_json(normalized, player_token=player_token)


@party_games_bp.post("/api/rooms/<code>/leave")
@rate_limit("party.room_action", 120, 60)
def leave_room(code):
    normalized = party_games.normalize_code(code)
    player_token = _session_token(PLAYER_SESSION_KEY, normalized)
    if player_token:
        party_games.leave_room(normalized, player_token)
        _remove_session_token(PLAYER_SESSION_KEY, normalized)
    return jsonify({"ok": True, "redirect": url_for("party_games.index", code=normalized)})


@party_games_bp.post("/api/rooms/<code>/scenes/answer")
@rate_limit("party.room_action", 120, 60)
def scenes_answer(code):
    normalized = party_games.normalize_code(code)
    player_token = _session_token(PLAYER_SESSION_KEY, normalized)
    try:
        scenes_phone.submit_answer(normalized, player_token or "", request.get_json(silent=True) or {})
    except scenes_phone.ScenesError as exc:
        return jsonify({"error": str(exc)}), 400
    return _snapshot_json(
        normalized,
        host_token=_session_token(HOST_SESSION_KEY, normalized),
        player_token=player_token,
    )


@party_games_bp.post("/api/rooms/<code>/scenes/vote")
@rate_limit("party.room_action", 120, 60)
def scenes_vote(code):
    normalized = party_games.normalize_code(code)
    player_token = _session_token(PLAYER_SESSION_KEY, normalized)
    payload = request.get_json(silent=True) or {}
    try:
        scenes_phone.submit_vote(normalized, player_token or "", int(payload.get("answer_id") or 0))
    except (ValueError, scenes_phone.ScenesError) as exc:
        return jsonify({"error": str(exc)}), 400
    return _snapshot_json(
        normalized,
        host_token=_session_token(HOST_SESSION_KEY, normalized),
        player_token=player_token,
    )


@party_games_bp.post("/api/rooms/<code>/scenes/next")
@rate_limit("party.room_action", 120, 60)
def scenes_next(code):
    normalized = party_games.normalize_code(code)
    host_token = _session_token(HOST_SESSION_KEY, normalized)
    try:
        scenes_phone.next_round_or_results(normalized, host_token or "")
    except scenes_phone.ScenesError as exc:
        return jsonify({"error": str(exc)}), 400
    return _snapshot_json(
        normalized,
        host_token=host_token,
        player_token=_session_token(PLAYER_SESSION_KEY, normalized),
    )


def _snapshot(code: str, *, host_token: str | None = None, player_token: str | None = None):
    snapshot = party_games.snapshot_room(code, host_token=host_token, player_token=player_token)
    if not snapshot:
        return None
    snapshot["room"]["game_title"] = _game_for_snapshot(snapshot)["title"]
    snapshot["room"]["game_description"] = _game_for_snapshot(snapshot)["description"]
    snapshot["room"]["player_range"] = _game_for_snapshot(snapshot)["player_range"]
    if snapshot["room"]["game_key"] == scenes_phone.GAME_KEY:
        snapshot = scenes_phone.enrich_snapshot(code, snapshot)
    return snapshot


def _snapshot_json(code: str, *, host_token: str | None = None, player_token: str | None = None):
    snapshot = _snapshot(code, host_token=host_token, player_token=player_token)
    if not snapshot:
        return jsonify({"error": "Room not found."}), 404
    return jsonify(snapshot)


def _game_for_snapshot(snapshot: dict):
    return PARTY_GAME_CATALOG.get(snapshot["room"]["game_key"], PARTY_GAME_CATALOG["lobby-test"])


def _session_token(key: str, code: str) -> str | None:
    values = session.get(key)
    if not isinstance(values, dict):
        return None
    token = values.get(code)
    return token if isinstance(token, str) else None


def _store_session_token(key: str, code: str, token: str) -> None:
    values = session.get(key)
    if not isinstance(values, dict):
        values = {}
    values[code] = token
    session[key] = values
    session.modified = True


def _remove_session_token(key: str, code: str) -> None:
    values = session.get(key)
    if not isinstance(values, dict):
        return
    values.pop(code, None)
    session[key] = values
    session.modified = True
