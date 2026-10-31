"""Authoritative multiplayer regression tests; uses only temporary SQLite data."""
import json
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
import uuid

import chess
from flask import Flask

from models import battle_chess as rooms, db
from routes.battle_chess import battle_chess_bp
from security import validate_csrf


def test_app():
    app = Flask(__name__, static_folder=str(Path(__file__).resolve().parents[1] / 'static'))
    app.config.update(TESTING=True, SECRET_KEY='battle-chess-test', RATE_LIMIT_ENABLED=False)
    app.before_request(validate_csrf)
    app.register_blueprint(battle_chess_bp, url_prefix='/games/battle-chess/api')
    return app


class BattleChessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(db, '_SQLITE_PATH', str(Path(self.tmp.name) / 'test.db')),
                        patch.object(db, 'DATABASE_URL', None)]
        for p in self.patches:
            p.start()
        rooms.init_tables()
        self.app = test_app()
        self.clients = [self.app.test_client() for _ in range(3)]
        self.csrf = [c.get('/games/battle-chess/api/session').json['csrfToken'] for c in self.clients]
        self.tokens = [None, None, None]
        self.room = None

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def post(self, player, path, body, csrf=True):
        headers = {'X-Battle-Token': self.tokens[player] or ''}
        if csrf:
            headers['X-CSRF-Token'] = self.csrf[player]
        return self.clients[player].post('/games/battle-chess/api' + path, json=body, headers=headers)

    def create(self, options=None):
        response = self.post(0, '/rooms', {'name': 'Alice', 'options': options or {}})
        self.assertEqual(response.status_code, 201)
        self.room = response.json['room']
        self.code = self.room['code']
        self.tokens[0] = response.json['token']

    def join(self):
        response = self.post(1, f'/rooms/{self.code}/join', {'name': 'Bob'})
        self.assertEqual(response.status_code, 200)
        self.room = response.json['room']
        self.tokens[1] = response.json['token']

    def action(self, player, kind, status=200, **extra):
        data = {'id': uuid.uuid4().hex, 'version': self.room['version'], 'type': kind, **extra}
        response = self.post(player, f'/rooms/{self.code}/actions', data)
        self.assertEqual(response.status_code, status, response.text)
        if status == 200:
            self.room = response.json['room']
        return response

    def move(self, player, source, target, **extra):
        return self.action(player, 'move', **{'from': source, 'to': target}, **extra)

    def seed(self, fen=None, deck=None):
        with rooms._locked_room(self.code) as (_, room):
            if fen:
                room['fen'] = fen
                room['positions'] = [rooms._position(chess.Board(fen))]
            if deck:
                room['battle']['deck'] = deck

    def capture(self):
        self.move(0, 'e2', 'e4')
        self.move(1, 'd7', 'd5')
        self.move(0, 'e4', 'd5')
        self.assertEqual(self.room['phase'], 'battle')

    def finish_cards(self, attacker_wins=True):
        deck = list(range(52))
        if attacker_wins:
            deck[0], deck[12] = deck[12], deck[0]
        self.seed(deck=deck)
        attacker = 0 if self.room['battle']['attacker'] == 'w' else 1
        self.action(attacker, 'pick', index=0)
        self.action(1 - attacker, 'pick', index=1)
        self.action(0, 'continue')
        self.action(1, 'continue')

    def test_lobby_auth_full_room_csrf_and_refresh(self):
        self.assertEqual(self.post(0, '/rooms', {'name': 'Alice'}, csrf=False).status_code, 400)
        self.create()
        self.assertEqual(self.room['phase'], 'waiting')
        self.assertEqual(self.room['you'], 'w')
        self.assertNotIn('token', json.dumps(self.room))
        self.join()
        self.assertEqual(self.room['you'], 'b')
        self.assertEqual(self.post(2, f'/rooms/{self.code}/join', {'name': 'Third'}).status_code, 409)
        self.assertEqual(self.clients[2].get(f'/games/battle-chess/api/rooms/{self.code}').status_code, 403)
        self.move(0, 'e2', 'e4')
        fresh = self.app.test_client()
        response = fresh.get(f'/games/battle-chess/api/rooms/{self.code}', headers={'X-Battle-Token': self.tokens[0]})
        self.assertEqual(response.json['room']['fen'], self.room['fen'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        rejoin = self.post(0, f'/rooms/{self.code}/join', {'name': 'Ignored'})
        self.assertEqual(rejoin.json['room']['you'], 'w')

    def test_turn_legal_moves_stale_commands_and_retry(self):
        self.create({'mode': 'classic'})
        self.join()
        self.move(1, 'e7', 'e5', status=409)
        self.move(0, 'e2', 'e5', status=400)
        version = self.room['version']
        action_id = uuid.uuid4().hex
        self.move(0, 'e2', 'e4', id=action_id)
        fen = self.room['fen']
        self.move(0, 'e2', 'e4', id=action_id, version=version)
        self.assertEqual(self.room['fen'], fen)
        self.move(1, 'e7', 'e5', version=version, status=409)
        self.action(0, 'replace-board', fen=chess.STARTING_FEN, status=409)

    def test_capture_hides_deck_and_enforces_picks(self):
        self.create()
        self.join()
        self.capture()
        self.assertNotIn('deck', json.dumps(self.room))
        self.assertIsNone(self.room['battle']['cards'])
        self.action(1, 'pick', index=1, status=409)
        self.action(0, 'pick', index=52, status=400)
        self.action(0, 'pick', index=True, status=400)
        self.action(0, 'continue', status=400)
        self.action(0, 'pick', index=0)
        self.assertIsNone(self.room['battle']['cards'])
        self.action(0, 'pick', index=2, status=409)
        self.action(1, 'pick', index=0, status=400)
        self.action(1, 'pick', index=1)
        self.assertEqual(len(self.room['battle']['cards']), 2)
        self.assertNotIn('deck', json.dumps(self.room))

    def test_attacker_wins_executes_capture_once(self):
        self.create()
        self.join()
        self.capture()
        self.finish_cards(True)
        board = chess.Board(self.room['fen'])
        self.assertIsNone(board.piece_at(chess.E4))
        self.assertEqual(board.piece_at(chess.D5).symbol(), 'P')
        self.assertEqual(self.room['phase'], 'playing')
        self.assertFalse(board.turn)

    def test_attacker_loss_retains_or_removes_piece_and_passes_turn(self):
        for color in (chess.WHITE, chess.BLACK):
            for removes in (False, True):
                with self.subTest(color=color, removes=removes):
                    self.create({'attackerLosesPiece': removes})
                    self.join()
                    before = chess.Board('4k3/8/8/3p4/4P3/8/8/4K3 w - - 7 12')
                    source, target = chess.E4, chess.D5
                    if color == chess.BLACK:
                        before = before.mirror()
                        source, target = chess.square_mirror(source), chess.square_mirror(target)
                    self.seed(fen=before.fen())
                    self.move(0 if color else 1, chess.square_name(source), chess.square_name(target))
                    self.finish_cards(False)
                    board = chess.Board(self.room['fen'])
                    self.assertEqual(board.piece_at(source) is None, removes)
                    self.assertEqual(board.piece_at(target), before.piece_at(target))
                    self.assertEqual(board.turn, not color)
                    self.assertIsNone(board.ep_square)
                    self.assertEqual(board.halfmove_clock, 0 if removes else 8)
                    self.assertEqual(board.fullmove_number, 12 if color else 13)
                    self.assertEqual(self.room['phase'], 'playing')
                    self.assertIsNone(self.room['result'])

    def test_ties_replay_or_use_selected_advantage(self):
        for advantage in ('none', 'attacker', 'defender'):
            with self.subTest(advantage=advantage):
                self.create({'advantage': advantage})
                self.join()
                self.capture()
                self.seed(deck=list(range(52)))
                battle_id = self.room['battle']['id']
                self.action(0, 'pick', index=0)
                self.action(1, 'pick', index=13)
                self.assertEqual(self.room['battle']['outcome'], 'tie' if advantage == 'none' else advantage)
                self.action(0, 'continue')
                self.action(1, 'continue')
                if advantage == 'none':
                    self.assertNotEqual(self.room['battle']['id'], battle_id)
                    self.assertEqual(self.room['battle']['picks'], {})
                else:
                    self.assertEqual(self.room['phase'], 'playing')

    def test_failed_capture_in_check_preserves_king_and_allows_another_reply(self):
        for color in (chess.WHITE, chess.BLACK):
            for removes in (False, True):
                with self.subTest(color=color, removes=removes):
                    self.create({'attackerLosesPiece': removes})
                    self.join()
                    before = chess.Board('4k3/8/8/8/8/8/4r3/4K3 w - - 17 8')
                    source, target, reply = chess.E1, chess.E2, chess.D1
                    if color == chess.BLACK:
                        before = before.mirror()
                        source, target, reply = map(chess.square_mirror, (source, target, reply))
                    self.seed(fen=before.fen())
                    player = 0 if color else 1
                    self.move(player, chess.square_name(source), chess.square_name(target))
                    self.finish_cards(False)
                    board = chess.Board(self.room['fen'])
                    self.assertEqual(self.room['phase'], 'playing')
                    self.assertIsNone(self.room['result'])
                    self.assertTrue(board.is_valid())
                    self.assertTrue(board.is_check())
                    self.assertEqual(board.turn, color)
                    self.assertEqual(board.king(color), source)
                    self.assertEqual(board.piece_at(target), before.piece_at(target))
                    self.assertEqual(board.halfmove_clock, 17)
                    self.assertEqual(board.fullmove_number, 8)
                    self.move(player, chess.square_name(source), chess.square_name(reply))
                    self.assertFalse(chess.Board(self.room['fen']).is_check())

    def test_failed_king_capture_keeps_valid_position_and_passes_when_not_in_check(self):
        for color in (chess.WHITE, chess.BLACK):
            with self.subTest(color=color):
                self.create({'attackerLosesPiece': True})
                self.join()
                before = chess.Board('4k3/8/8/8/8/8/P2n4/4K3 w - - 13 4')
                source, target = chess.E1, chess.D2
                if color == chess.BLACK:
                    before = before.mirror()
                    source, target = chess.square_mirror(source), chess.square_mirror(target)
                self.seed(fen=before.fen())
                self.move(0 if color else 1, chess.square_name(source), chess.square_name(target))
                self.finish_cards(False)
                board = chess.Board(self.room['fen'])
                self.assertEqual(self.room['phase'], 'playing')
                self.assertIsNone(self.room['result'])
                self.assertTrue(board.is_valid())
                self.assertEqual(board.king(color), source)
                self.assertEqual(board.piece_at(target), before.piece_at(target))
                self.assertEqual(board.turn, not color)
                self.assertEqual(board.halfmove_clock, 14)
                self.assertEqual(board.fullmove_number, 4 if color else 5)

    def test_failed_nonking_capture_while_checked_retains_turn_after_optional_removal(self):
        for color in (chess.WHITE, chess.BLACK):
            for removes in (False, True):
                with self.subTest(color=color, removes=removes):
                    self.create({'attackerLosesPiece': removes})
                    self.join()
                    before = chess.Board('4k3/8/8/8/8/8/R3r3/4K3 w - - 19 9')
                    source, target = chess.A2, chess.E2
                    if color == chess.BLACK:
                        before = before.mirror()
                        source, target = chess.square_mirror(source), chess.square_mirror(target)
                    self.seed(fen=before.fen())
                    self.move(0 if color else 1, chess.square_name(source), chess.square_name(target))
                    self.finish_cards(False)
                    board = chess.Board(self.room['fen'])
                    self.assertEqual(self.room['phase'], 'playing')
                    self.assertIsNone(self.room['result'])
                    self.assertEqual(board.piece_at(source) is None, removes)
                    self.assertEqual(board.piece_at(target), before.piece_at(target))
                    self.assertEqual(board.turn, color)
                    self.assertTrue(board.is_check())
                    self.assertTrue(board.is_valid())
                    self.assertEqual(board.halfmove_clock, 0 if removes else 19)
                    self.assertEqual(board.fullmove_number, 9)

    def test_failed_pinned_attacker_only_retains_turn_if_removal_exposes_check(self):
        for color in (chess.WHITE, chess.BLACK):
            for removes in (False, True):
                with self.subTest(color=color, removes=removes):
                    self.create({'attackerLosesPiece': removes})
                    self.join()
                    before = chess.Board('4r1k1/8/8/8/8/8/4R3/4K3 w - - 21 11')
                    source, target = chess.E2, chess.E8
                    if color == chess.BLACK:
                        before = before.mirror()
                        source, target = chess.square_mirror(source), chess.square_mirror(target)
                    self.seed(fen=before.fen())
                    self.move(0 if color else 1, chess.square_name(source), chess.square_name(target))
                    self.finish_cards(False)
                    board = chess.Board(self.room['fen'])
                    self.assertEqual(self.room['phase'], 'playing')
                    self.assertIsNone(self.room['result'])
                    self.assertEqual(board.piece_at(source) is None, removes)
                    self.assertEqual(board.piece_at(target), before.piece_at(target))
                    self.assertEqual(board.turn, color if removes else not color)
                    self.assertEqual(board.is_check(), removes)
                    self.assertTrue(board.is_valid())
                    self.assertEqual(board.halfmove_clock, 0 if removes else 22)
                    self.assertEqual(board.fullmove_number, 11 + int(not color and not removes))

    def test_failed_rook_capture_clears_only_removed_rooks_castling_right(self):
        for color in (chess.WHITE, chess.BLACK):
            for source in (chess.A1, chess.H1):
                with self.subTest(color=color, source=source):
                    self.create({'attackerLosesPiece': True})
                    self.join()
                    before = chess.Board('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 37 23')
                    target = chess.square(chess.square_file(source), 7)
                    if color == chess.BLACK:
                        before = before.mirror()
                        source, target = chess.square_mirror(source), chess.square_mirror(target)
                    self.seed(fen=before.fen())
                    self.move(0 if color else 1, chess.square_name(source), chess.square_name(target))
                    self.finish_cards(False)
                    board = chess.Board(self.room['fen'])
                    self.assertIsNone(board.piece_at(source))
                    self.assertEqual(board.castling_rights, before.castling_rights & ~chess.BB_SQUARES[source])
                    self.assertEqual(board.turn, not color)
                    self.assertEqual(board.halfmove_clock, 0)
                    self.assertEqual(board.fullmove_number, 23 if color else 24)
                    self.assertTrue(board.is_valid())

    def test_failed_en_passant_clears_opportunity_and_preserves_defending_pawn(self):
        for color in (chess.WHITE, chess.BLACK):
            for removes in (False, True):
                with self.subTest(color=color, removes=removes):
                    self.create({'attackerLosesPiece': removes})
                    self.join()
                    before = chess.Board('4k3/8/8/3pP3/8/8/8/4K3 w - d6 33 24')
                    source, target, defender = chess.E5, chess.D6, chess.D5
                    if color == chess.BLACK:
                        before = before.mirror()
                        source, target, defender = map(chess.square_mirror, (source, target, defender))
                    self.seed(fen=before.fen(en_passant='fen'))
                    self.move(0 if color else 1, chess.square_name(source), chess.square_name(target))
                    self.finish_cards(False)
                    board = chess.Board(self.room['fen'])
                    self.assertIsNone(board.ep_square)
                    self.assertEqual(board.piece_at(source) is None, removes)
                    self.assertEqual(board.piece_at(defender), before.piece_at(defender))
                    self.assertIsNone(board.piece_at(target))
                    self.assertEqual(board.turn, not color)
                    self.assertEqual(board.halfmove_clock, 0 if removes else 34)
                    self.assertEqual(board.fullmove_number, 24 if color else 25)

    def test_failed_capture_still_uses_normal_draw_detection_after_removal(self):
        self.create({'attackerLosesPiece': True})
        self.join()
        self.seed(fen='4k3/8/8/8/8/8/3nR3/4K3 w - - 9 3')
        self.move(0, 'e2', 'd2')
        self.finish_cards(False)
        self.assertEqual(self.room['phase'], 'finished')
        self.assertEqual(self.room['result'], {'winner': None, 'reason': 'draw'})
        self.assertIsNone(chess.Board(self.room['fen']).piece_at(chess.E2))

    def test_promotion_en_passant_and_castling(self):
        self.create()
        self.join()
        self.seed(fen='1r5k/P7/8/8/8/8/8/7K w - - 0 1')
        self.move(0, 'a7', 'b8', promotion='n')
        self.finish_cards(True)
        self.assertEqual(chess.Board(self.room['fen']).piece_at(chess.B8).symbol(), 'N')
        self.create()
        self.join()
        self.seed(fen='4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1')
        self.move(0, 'e5', 'd6')
        self.finish_cards(True)
        board = chess.Board(self.room['fen'])
        self.assertIsNone(board.piece_at(chess.D5))
        self.assertEqual(board.piece_at(chess.D6).symbol(), 'P')
        self.create({'mode': 'classic'})
        self.join()
        self.seed(fen='r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
        self.move(0, 'e1', 'g1')
        board = chess.Board(self.room['fen'])
        self.assertEqual(board.piece_at(chess.F1).symbol(), 'R')

    def test_checkmate_rematch_and_leave(self):
        self.create({'mode': 'classic'})
        self.join()
        for player, source, target in [(0, 'f2', 'f3'), (1, 'e7', 'e5'), (0, 'g2', 'g4'), (1, 'd8', 'h4')]:
            self.move(player, source, target)
        self.assertEqual(self.room['result'], {'winner': 'b', 'reason': 'checkmate'})
        self.action(0, 'rematch')
        self.assertEqual(self.room['phase'], 'finished')
        self.action(1, 'rematch')
        self.assertEqual(self.room['fen'], chess.STARTING_FEN)
        self.action(1, 'leave')
        self.assertEqual(self.room['result']['winner'], 'w')
        self.action(0, 'rematch', status=400)
        self.action(1, 'move', status=403)

    def test_repetition_draw_survives_polling(self):
        self.create({'mode': 'classic'})
        self.join()
        for _ in range(2):
            for player, source, target in [(0, 'g1', 'f3'), (1, 'g8', 'f6'), (0, 'f3', 'g1'), (1, 'f6', 'g8')]:
                self.move(player, source, target)
                rooms.get_room(self.code, self.tokens[player])
        self.assertEqual(self.room['result']['reason'], 'draw')

    def test_presence_expiry_and_input_validation(self):
        for payload in ({'name': ''}, {'name': 7}, {'name': 'x' * 25}, {'name': 'A', 'options': []}, {'name': 'A', 'options': {'mode': 'bad'}}):
            self.assertEqual(self.post(0, '/rooms', payload).status_code, 400)
        self.create()
        self.join()
        with rooms._locked_room(self.code) as (_, room):
            room['players']['b']['seen'] -= 60
        state = rooms.get_room(self.code, self.tokens[0])
        self.assertFalse(state['players']['b']['online'])
        rooms.get_room(self.code, self.tokens[1])
        self.assertTrue(rooms.get_room(self.code, self.tokens[0])['players']['b']['online'])
        with patch.object(rooms.time, 'time', return_value=rooms.time.time() + rooms.ROOM_LIFETIME + 1):
            with self.assertRaises(rooms.RoomError) as caught:
                rooms.get_room(self.code, self.tokens[0])
            self.assertEqual(caught.exception.status, 404)

    def test_simultaneous_join_and_move_are_atomic(self):
        self.create({'mode': 'classic'})
        def join(name):
            try:
                return rooms.join_room(self.code, name)[0]['you']
            except rooms.RoomError as exc:
                return exc.status
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(join, ['One', 'Two']))
        self.assertCountEqual(results, ['b', 409])
        state = rooms.get_room(self.code, self.tokens[0])
        def move(target):
            try:
                return rooms.act(self.code, self.tokens[0], {'id': uuid.uuid4().hex, 'version': state['version'],
                    'type': 'move', 'from': 'e2', 'to': target})['version']
            except rooms.RoomError as exc:
                return exc.status
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(move, ['e3', 'e4']))
        self.assertCountEqual(results, [state['version'] + 1, 409])


if __name__ == '__main__':
    unittest.main()
