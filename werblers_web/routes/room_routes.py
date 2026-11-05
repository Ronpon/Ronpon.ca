"""Private guest-room endpoints. Writes use the site's existing CSRF checks."""
from flask import Blueprint, jsonify, request
from security import json_body, rate_limit
from werblers_web import rooms

room_bp = Blueprint('werblers_rooms', __name__)


@room_bp.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@room_bp.errorhandler(rooms.RoomError)
def room_error(error):
    return jsonify(error=str(error)), error.status


def seat_token():
    return request.headers.get('X-Werblers-Token', '')[:128]


@room_bp.post('/rooms')
@rate_limit('werblers.rooms.create', 20, 3600)
def create_room():
    data = json_body()
    room, token = rooms.create(data.get('name'), data.get('mode', 'live'))
    return jsonify(room=room, token=token), 201


@room_bp.post('/rooms/<code>/join')
@rate_limit('werblers.rooms.join', 60, 600)
def join_room(code):
    room, token = rooms.join(code, json_body().get('name'), seat_token())
    return jsonify(room=room, token=token)


@room_bp.get('/rooms/<code>')
@rate_limit('werblers.rooms.poll', 240, 60)
def get_room(code):
    return jsonify(room=rooms.get(code, seat_token()))


@room_bp.post('/rooms/<code>/actions/<action>')
@rate_limit('werblers.rooms.action', 120, 60)
def room_action(code, action):
    return jsonify(room=rooms.action(code, seat_token(), action, json_body()))
