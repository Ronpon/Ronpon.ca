"""Same-origin JSON API for Battle Chess. All writes use the site's CSRF check."""
from flask import Blueprint, jsonify, request

from models import battle_chess as rooms
from security import csrf_token, json_body, rate_limit

battle_chess_bp = Blueprint("battle_chess", __name__)


@battle_chess_bp.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@battle_chess_bp.errorhandler(rooms.RoomError)
def room_error(exc):
    return jsonify(error=str(exc)), exc.status


def token():
    return request.headers.get("X-Battle-Token", "")[:128]


@battle_chess_bp.get("/session")
def session_info():
    return jsonify(csrfToken=csrf_token())


@battle_chess_bp.post("/rooms")
@rate_limit("chess.create", 20, 3600)
def create_room():
    body = json_body()
    state, seat_token = rooms.create_room(body.get("name"), body.get("options", {}))
    return jsonify(room=state, token=seat_token), 201


@battle_chess_bp.post("/rooms/<code>/join")
@rate_limit("chess.join", 60, 600)
def join_room(code):
    state, seat_token = rooms.join_room(code, json_body().get("name"), token())
    return jsonify(room=state, token=seat_token)


@battle_chess_bp.get("/rooms/<code>")
@rate_limit("chess.poll", 1200, 60)
def room_state(code):
    return jsonify(room=rooms.get_room(code, token()))


@battle_chess_bp.post("/rooms/<code>/actions")
@rate_limit("chess.action", 120, 60)
def room_action(code):
    return jsonify(room=rooms.act(code, token(), json_body()))


@battle_chess_bp.post('/rooms/<code>/battle-input')
@rate_limit('chess.controls', 3600, 60)
def battle_input(code):
    return jsonify(room=rooms.battle_input(code, token(), json_body()))
