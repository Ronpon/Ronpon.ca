"""Authoritative, persistent two-player Battle Chess rooms.

Room mutations use database locks, so multiple workers cannot accept conflicting
moves or a third player. Clients never supply a board or a battle outcome.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import json
import re
import secrets
import time

import chess

from models.db import get_conn, is_postgres, ph
from models import chess_minigames as minigames

ROOM_LIFETIME = 24 * 60 * 60
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class RoomError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def init_tables():
    with get_conn() as conn:
        conn.cursor().execute("""CREATE TABLE IF NOT EXISTS battle_chess_rooms (
            code TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at DOUBLE PRECISION NOT NULL
        )""")


def normalize_code(value):
    code = value.strip().upper() if isinstance(value, str) else ""
    if not re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", code):
        raise RoomError("Enter a valid six-character room code.")
    return code


def clean_name(value):
    if not isinstance(value, str):
        raise RoomError("Enter your name (1–24 characters).")
    name = " ".join(value.split())
    if not name or len(name) > 24 or any(ord(c) < 32 for c in name):
        raise RoomError("Enter your name (1–24 characters).")
    return name


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _player(name, token):
    return {"name": clean_name(name), "token": _token_hash(token),
            "seen": time.time(), "left": False, "lastAction": None}


def _new_game(room):
    room['game'] = room.get('game', 0) + 1
    room['battleIndex'] = 0
    room.update(fen=chess.STARTING_FEN, phase="playing", battle=None,
                result=None, lastMove=None, rematch=[], positions=[_position(chess.Board())])


def create_room(name, options):
    if not isinstance(options, dict):
        raise RoomError("Invalid game settings.")
    mode = options.get("mode", "highest-card")
    advantage = options.get("advantage", "attacker")
    loses_piece = options.get("attackerLosesPiece", False)
    if mode not in (*minigames.GAMES, "mixed", "classic") or advantage not in ("attacker", "defender", "none") or type(loses_piece) is not bool:
        raise RoomError("Invalid game settings.")
    selected = options.get('selectedMinigames', list(minigames.GAMES)) if mode == 'mixed' else ([] if mode == 'classic' else [mode])
    selection = options.get('minigameMode', 'random')
    if not isinstance(selected, list) or len(selected) > 5 or any(not isinstance(g, str) or g not in minigames.GAMES for g in selected) or len(set(selected)) != len(selected) or (mode == 'mixed' and not selected) or selection not in ('random', 'setOrder', 'attackerChoice', 'defenderChoice'):
        raise RoomError('Choose at least one valid minigame and selection mode.')
    token = secrets.token_urlsafe(32)
    room = {"version": 1, "players": {"w": _player(name, token), "b": None},
            "options": {"mode": mode, "advantage": advantage, "attackerLosesPiece": loses_piece,
                        'selectedMinigames': selected, 'minigameMode': selection}}
    _new_game(room)
    room["phase"] = "waiting"
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM battle_chess_rooms WHERE updated_at < {ph()}", (time.time() - ROOM_LIFETIME,))
        for _ in range(10):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            cur.execute(f"INSERT INTO battle_chess_rooms (code, state, updated_at) VALUES ({ph(3)}) ON CONFLICT (code) DO NOTHING",
                        (code, json.dumps(room), time.time()))
            if cur.rowcount:
                return snapshot(code, room, "w"), token
    raise RoomError("Could not create a room. Try again.", 503)


@contextmanager
def _locked_room(code):
    code = normalize_code(code)
    with get_conn() as conn:
        cur = conn.cursor()
        if not is_postgres():
            cur.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if is_postgres() else ""
        cur.execute(f"SELECT state, updated_at FROM battle_chess_rooms WHERE code = {ph()}{lock}", (code,))
        row = cur.fetchone()
        if not row or row["updated_at"] < time.time() - ROOM_LIFETIME:
            raise RoomError("Room not found or expired. Create a new room.", 404)
        room = json.loads(row["state"])
        before = json.dumps(room)
        yield code, room
        if json.dumps(room) != before:
            cur.execute(f"UPDATE battle_chess_rooms SET state = {ph()}, updated_at = {ph()} WHERE code = {ph()}",
                        (json.dumps(room), time.time(), code))


def _authenticate(room, token):
    for color, player in room["players"].items():
        if player and token and hmac.compare_digest(player["token"], _token_hash(token)):
            return color
    raise RoomError("This browser has no seat in that room. Join with the room code.", 403)


def join_room(code, name, token=""):
    with _locked_room(code) as (code, room):
        if token:
            try:
                color = _authenticate(room, token)
                if not room["players"][color]["left"]:
                    return snapshot(code, room, color), token
            except RoomError:
                pass
        if room["phase"] != "waiting" or room["players"]["b"]:
            raise RoomError("This room is full or has already ended.", 409)
        token = secrets.token_urlsafe(32)
        room["players"]["b"] = _player(name, token)
        room["phase"] = "playing"
        room["version"] += 1
        return snapshot(code, room, "b"), token


def get_room(code, token):
    with _locked_room(code) as (code, room):
        color = _authenticate(room, token)
        player = room["players"][color]
        if not player["left"] and time.time() - player["seen"] > 10:
            player["seen"] = time.time()
        _advance(room)
        if room['battle']:
            minigames.signal_seen(room['battle'], color, time.time())
        return snapshot(code, room, color)


def snapshot(code, room, color):
    battle = room["battle"]
    public_battle = minigames.public(battle, color) if battle else None
    return {"code": code, "you": color, "version": room["version"], "game": room['game'], "fen": room["fen"],
            'serverTime': time.time(), 'battleIndex': room.get('battleIndex', 0),
            "phase": room["phase"], "options": room["options"], "battle": public_battle,
            "result": room["result"], "lastMove": room["lastMove"], "rematch": room["rematch"],
            "players": {side: ({"name": p["name"], "color": side, "left": p["left"],
                                  "online": not p["left"] and time.time() - p["seen"] < 35} if p else None)
                        for side, p in room["players"].items()}}


def act(code, token, payload):
    action_id = payload.get("id")
    if not isinstance(action_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{16,64}", action_id):
        raise RoomError("Invalid action identifier.")
    with _locked_room(code) as (code, room):
        color = _authenticate(room, token)
        player = room["players"][color]
        # A retry after a lost HTTP response must not play the action twice.
        if player["lastAction"] == action_id:
            return snapshot(code, room, color)
        if player["left"]:
            raise RoomError("You have left this room.", 403)
        kind = payload.get("type")
        # Controls and acknowledgements are scoped to the game/battle, not the
        # rapidly changing room revision. Chess moves still require a revision.
        scoped = payload.get('game') == room['game'] and (kind in ('leave', 'resign') or
            (kind in ('battle-ready', 'choose', 'flip', 'reveal', 'continue') and room['battle'] and payload.get('battleId') == room['battle']['id']))
        if not scoped and (type(payload.get("version")) is not int or payload["version"] != room["version"]):
            raise RoomError("The room changed. Syncing the latest position; please try again.", 409)
        _advance(room)
        if kind == "leave":
            player["left"] = True
            if room["phase"] != "finished":
                _finish(room, _other(color) if room["players"]["b"] else None, "opponent-left")
        elif kind == "resign" and room["phase"] in ("playing", "battle"):
            _finish(room, _other(color), "resignation")
        elif kind == "rematch" and room["phase"] == "finished":
            if not all(p and not p["left"] for p in room["players"].values()):
                raise RoomError("Your opponent has left. Create a new room.")
            if color not in room["rematch"]:
                room["rematch"].append(color)
            if len(room["rematch"]) == 2:
                _new_game(room)
        elif kind == "move" and room["phase"] == "playing":
            _move(room, color, payload)
        elif kind == "pick" and room["phase"] == "battle":
            _pick(room, color, payload)
        elif kind == "reveal" and room["phase"] == "battle":
            _reveal_cards(room)
        elif kind in ('choose', 'battle-ready', 'flip') and room['phase'] == 'battle':
            battle = room['battle']
            try:
                if kind == 'choose':
                    game = payload.get('gameId')
                    if battle.get('phase') != 'choose' or battle['choiceBy'] != color or game not in room['options']['selectedMinigames']:
                        raise minigames.BattleError('Only the designated player can choose an enabled minigame.')
                    room['battle'] = _battle(battle['attacker'], battle['move'], game, room['options']['advantage'])
                elif kind == 'battle-ready':
                    minigames.ready(battle, color, time.time())
                else:
                    minigames.flip(battle, color, payload.get('index'), payload.get('turnNumber'), time.time())
            except minigames.BattleError as exc:
                raise RoomError(str(exc), 409) from exc
        elif kind == "continue" and room["phase"] == "battle":
            battle = room["battle"]
            if battle["outcome"] is None:
                raise RoomError("Finish the battle first.")
            if color not in battle["ready"]:
                battle["ready"].append(color)
            if len(battle["ready"]) == 2:
                if battle["outcome"] == "tie":
                    room["battle"] = _battle(battle["attacker"], battle["move"], battle.get('gameId', 'highest-card'), room['options']['advantage'])
                else:
                    _resolve_battle(room)
        else:
            raise RoomError("That action is not available right now.", 409)
        player["lastAction"] = action_id
        player["seen"] = time.time()
        room["version"] += 1
        return snapshot(code, room, color)


def _advance(room):
    battle = room['battle']
    if battle and battle.get('gameId'):
        before = json.dumps(battle)
        minigames.advance(battle, time.time())
        if json.dumps(battle) != before:
            room['version'] += 1


def battle_input(code, token, payload):
    with _locked_room(code) as (code, room):
        color = _authenticate(room, token)
        player = room['players'][color]
        if player['left']:
            raise RoomError('You have left this room.', 403)
        battle = room['battle']
        if not battle or payload.get('battleId') != battle['id']:
            raise RoomError('This battle has ended. Sync the room.', 409)
        _advance(room)
        try:
            minigames.input_frame(battle, color, payload, time.time())
        except minigames.BattleError as exc:
            raise RoomError(str(exc)) from exc
        minigames.signal_seen(battle, color, time.time())
        player['seen'] = time.time()
        room['version'] += 1
        return snapshot(code, room, color)


def _other(color):
    return "b" if color == "w" else "w"


def _position(board):
    return " ".join(board.fen().split()[:4])


def _finish(room, winner, reason):
    room.update(phase="finished", result={"winner": winner, "reason": reason}, battle=None)


def _record(room, board):
    room["fen"] = board.fen(en_passant="fen")
    position = _position(board)
    room["positions"].append(position)
    if board.is_checkmate():
        _finish(room, "b" if board.turn else "w", "checkmate")
    elif board.is_stalemate():
        _finish(room, None, "stalemate")
    elif board.is_insufficient_material() or board.halfmove_clock >= 100 or room["positions"].count(position) >= 3:
        _finish(room, None, "draw")


def _move(room, color, payload):
    board = chess.Board(room["fen"])
    if board.turn != (color == "w"):
        raise RoomError("Wait for your turn.", 409)
    source, target, promotion = payload.get("from"), payload.get("to"), payload.get("promotion", "q")
    if not all(isinstance(s, str) and re.fullmatch(r"[a-h][1-8]", s) for s in (source, target)) or promotion not in ("q", "r", "b", "n"):
        raise RoomError("Invalid move.")
    piece = board.piece_at(chess.parse_square(source))
    promotes = piece and piece.piece_type == chess.PAWN and target[1] in "18"
    move = chess.Move.from_uci(source + target + (promotion if promotes else ""))
    if move not in board.legal_moves:
        raise RoomError("That move is not legal.")
    if board.is_capture(move) and room["options"]["mode"] != "classic":
        selected = room['options'].get('selectedMinigames', [room['options']['mode']])
        selection = room['options'].get('minigameMode', 'random')
        if len(selected) > 1 and selection in ('attackerChoice', 'defenderChoice'):
            room['battle'] = dict(id=secrets.token_hex(8), gameId=None, attacker=color, move=move.uci(),
                                  phase='choose', choiceBy=color if selection == 'attackerChoice' else _other(color), ready=[], outcome=None)
        else:
            game = selected[room.get('battleIndex', 0) % len(selected)] if selection == 'setOrder' else secrets.choice(selected)
            room['battle'] = _battle(color, move.uci(), game, room['options']['advantage'])
        room['battleIndex'] = room.get('battleIndex', 0) + 1
        room["phase"] = "battle"
    else:
        room["lastMove"] = {"from": source, "to": target}
        board.push(move)
        _record(room, board)


def _battle(attacker, move, game='highest-card', advantage='attacker'):
    return minigames.create(game, attacker, move, advantage, time.time())


def _pick(room, color, payload):
    battle = room["battle"]
    if battle.get('gameId', 'highest-card') != 'highest-card':
        raise RoomError('Highest Card is not running.', 409)
    picker = battle["attacker"] if not battle["picks"] else _other(battle["attacker"])
    index = payload.get("index")
    if color != picker or color in battle["picks"] or battle["outcome"] is not None:
        raise RoomError("Wait for your opponent to pick.", 409)
    if type(index) is not int or not 0 <= index < 52 or index in battle["picks"].values():
        raise RoomError("Choose an available card.")
    battle["picks"][color] = index
    if len(battle["picks"]) == 2:
        battle["phase"] = "reveal-ready"


def _reveal_cards(room):
    battle = room["battle"]
    if battle.get('gameId') != 'highest-card' or len(battle.get('picks', {})) != 2:
        raise RoomError("Both players must pick a card before the reveal.", 409)
    # Simultaneous Reveal clicks are safe and never resolve the capture twice.
    if battle["outcome"] is None:
        attacker = battle["attacker"]
        a = battle["deck"][battle["picks"][attacker]] % 13
        b = battle["deck"][battle["picks"][_other(attacker)]] % 13
        advantage = room["options"]["advantage"]
        battle["outcome"] = ("tie" if a == b and advantage == "none" else
                             "attacker" if a > b or (a == b and advantage == "attacker") else "defender")
        battle["phase"] = "result"


def _resolve_battle(room):
    battle = room["battle"]
    board = chess.Board(room["fen"])
    move = chess.Move.from_uci(battle["move"])
    room.update(phase="playing", battle=None)
    if battle["outcome"] == "attacker":
        room["lastMove"] = {"from": chess.square_name(move.from_square), "to": chess.square_name(move.to_square)}
        board.push(move)
    else:
        attacker = board.piece_at(move.from_square)
        remove_attacker = room["options"]["attackerLosesPiece"] and attacker.piece_type != chess.KING
        if remove_attacker:
            board.remove_piece_at(move.from_square)
            board.castling_rights = board.clean_castling_rights()
            board.halfmove_clock = 0
        board.ep_square = None
        # Losing a battle never forfeits the chess game. Keep kings on the board
        # and let a checked attacker make another legal reply on the same turn.
        if not board.is_check():
            if not remove_attacker:
                board.halfmove_clock += 1
            if not board.turn:
                board.fullmove_number += 1
            board.turn = not board.turn
        room["lastMove"] = None
    _record(room, board)
