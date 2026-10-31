"""Rules and network regressions for every online capture minigame."""
import time
import unittest
from unittest.mock import patch

from models import battle_chess as rooms, chess_minigames as games
import test_battle_chess as fixtures


class NetworkMinigameTests(unittest.TestCase):
    # Reuse the temporary-database/API fixtures without inheriting their tests.
    setUp = fixtures.BattleChessTests.setUp
    tearDown = fixtures.BattleChessTests.tearDown
    post = fixtures.BattleChessTests.post
    create = fixtures.BattleChessTests.create
    join = fixtures.BattleChessTests.join
    action = fixtures.BattleChessTests.action
    move = fixtures.BattleChessTests.move
    seed = fixtures.BattleChessTests.seed
    capture = fixtures.BattleChessTests.capture

    def start(self, game, **options):
        self.create({'mode': game, **options})
        self.join()
        self.capture()

    def pulse(self, player, **data):
        color = 'w' if player == 0 else 'b'
        state = rooms.get_room(self.code, self.tokens[player])
        data = dict(battleId=state['battle']['id'], seq=state['battle'].get('ack', 0) + 1, **data)
        self.room = rooms.battle_input(self.code, self.tokens[player], data)
        return self.room

    def test_every_game_can_be_selected_and_invalid_lists_rejected(self):
        for game in games.GAMES:
            with self.subTest(game=game):
                self.start(game)
                self.assertEqual(self.room['battle']['gameId'], game)
        for selected in ([], ['bogus'], ['memory-match'] * 2, [None], {}):
            response = self.post(0, '/rooms', {'name': 'A', 'options': {'mode': 'mixed', 'selectedMinigames': selected}})
            self.assertEqual(response.status_code, 400)

    def test_attacker_and_defender_choice_are_enforced(self):
        for mode, picker in [('attackerChoice', 0), ('defenderChoice', 1)]:
            self.start('mixed', minigameMode=mode, selectedMinigames=['memory-match', 'dodging-battle'])
            self.assertEqual(self.room['battle']['phase'], 'choose')
            self.action(1 - picker, 'choose', gameId='memory-match', status=409)
            self.action(picker, 'choose', gameId='highest-card', status=409)
            self.action(picker, 'choose', gameId='memory-match')
            self.assertEqual(self.room['battle']['gameId'], 'memory-match')

    def test_set_order_advances_only_on_new_capture(self):
        self.start('mixed', minigameMode='setOrder', selectedMinigames=['mashing-battle', 'memory-match'])
        self.assertEqual(self.room['battle']['gameId'], 'mashing-battle')
        with rooms._locked_room(self.code) as (_, room):
            games.finish(room['battle'], None)
        self.action(0, 'continue')
        self.action(1, 'continue')
        self.assertEqual(self.room['battle']['gameId'], 'mashing-battle')
        with rooms._locked_room(self.code) as (_, room):
            games.finish(room['battle'], 'w')
        self.action(0, 'continue')
        self.action(1, 'continue')
        self.move(1, 'd8', 'd5')
        self.assertEqual(self.room['battle']['gameId'], 'memory-match')

    def test_memory_turns_hidden_cards_and_two_second_reveal(self):
        self.start('memory-match')
        self.seed(deck=list(range(52)))
        self.action(1, 'flip', index=0, turnNumber=1, status=409)
        self.action(0, 'flip', index=0, turnNumber=1)
        self.assertEqual(self.room['battle']['cards'], {'0': 0})
        self.assertNotIn('deck', str(self.room))
        self.action(0, 'flip', index=0, turnNumber=1, status=409)
        self.action(0, 'flip', index=1, turnNumber=1)
        self.action(0, 'flip', index=2, turnNumber=1)
        hide = self.room['battle']['hideAt']
        self.assertEqual(len(self.room['battle']['cards']), 3)
        self.action(0, 'flip', index=3, turnNumber=1, status=409)
        with patch.object(rooms.time, 'time', return_value=hide - .01):
            state = rooms.get_room(self.code, self.tokens[0])
            self.assertEqual(len(state['battle']['cards']), 3)
        with patch.object(rooms.time, 'time', return_value=hide + .01):
            self.room = rooms.get_room(self.code, self.tokens[1])
            self.assertEqual(self.room['battle']['cards'], {})
            self.assertEqual(self.room['battle']['turn'], 'b')
            self.action(1, 'flip', index=0, turnNumber=1, status=409)
            self.action(1, 'flip', index=0, turnNumber=2)

    def test_memory_match_resolves_the_shared_capture(self):
        self.start('memory-match')
        self.seed(deck=list(range(52)))
        for index in [0, 13, 26]:
            self.action(0, 'flip', index=index, turnNumber=1)
        self.assertEqual(self.room['battle']['outcome'], 'attacker')
        self.action(0, 'continue')
        self.action(1, 'continue')
        self.assertEqual(self.room['lastMove'], {'from': 'e4', 'to': 'd5'})

    def test_live_input_ownership_sequence_validation_and_csrf(self):
        self.start('mashing-battle', advantage='none')
        self.action(0, 'battle-ready')
        self.assertEqual(self.room['battle']['phase'], 'ready')
        self.action(1, 'battle-ready')
        self.assertEqual(self.room['battle']['phase'], 'countdown')
        with rooms._locked_room(self.code) as (_, room):
            room['battle'].update(phase='playing', startAt=time.time() - 1, endsAt=time.time() + 20)
        payload = dict(battleId=self.room['battle']['id'], seq=1, taps=5)
        first = rooms.battle_input(self.code, self.tokens[0], payload)
        retry = rooms.battle_input(self.code, self.tokens[0], payload)
        self.assertEqual(first['battle']['presses']['w'], 5)
        self.assertEqual(retry['battle']['presses']['w'], 5)
        self.assertEqual(retry['battle']['presses']['b'], 0)
        self.assertEqual(self.post(0, f'/rooms/{self.code}/battle-input', {**payload, 'seq': 2}, csrf=False).status_code, 400)
        for invalid in ({'seq': True}, {'keys': 16}, {'taps': 1000}, {'taps': -1}):
            response = self.post(0, f'/rooms/{self.code}/battle-input', {**payload, **invalid})
            self.assertEqual(response.status_code, 400)
        with self.assertRaises(rooms.RoomError):
            rooms.battle_input(self.code, 'not-a-seat', payload)
        self.assertEqual(self.post(0, f'/rooms/{self.code}/battle-input', {**payload, 'battleId': 'old-round'}).status_code, 409)

    def test_live_disconnect_pauses_and_requires_both_to_resume(self):
        self.start('mashing-battle')
        self.action(0, 'battle-ready')
        self.action(1, 'battle-ready')
        now = time.time()
        with rooms._locked_room(self.code) as (_, room):
            room['battle'].update(phase='playing', startAt=now - 5, endsAt=now + 15)
            room['battle']['lastSeen']['b'] = now - 4
        self.room = rooms.get_room(self.code, self.tokens[0])
        self.assertEqual(self.room['battle']['phase'], 'paused')
        ends = self.room['battle']['endsAt']
        self.action(0, 'battle-ready')
        self.assertEqual(self.room['battle']['phase'], 'paused')
        self.action(1, 'battle-ready')
        self.assertEqual(self.room['battle']['phase'], 'countdown')
        self.assertGreater(self.room['battle']['endsAt'], ends)
        self.assertIsNone(self.room['battle']['outcome'])


class MinigameSimulationTests(unittest.TestCase):
    def game(self, game, advantage='none'):
        b = games.create(game, 'w', 'e4d5', advantage, 0)
        if game in games.LIVE_GAMES:
            games.ready(b, 'w', 0)
            games.ready(b, 'b', 0)
            self.advance(b, 3)
        return b

    def advance(self, b, now):
        b['lastSeen'] = {'w': now, 'b': now}
        games.advance(b, now)

    def test_mashing_counts_both_players_caps_bursts_and_ends_at_twenty_seconds(self):
        b = self.game('mashing-battle')
        games.input_frame(b, 'w', {'seq': 1, 'taps': 5}, 3.1)
        games.input_frame(b, 'b', {'seq': 1, 'taps': 5}, 3.1)
        self.assertEqual(b['position'], 4)
        games.input_frame(b, 'w', {'seq': 2, 'taps': 8}, 3.1)
        self.assertEqual(b['presses']['w'], 8)  # only the remaining burst budget
        games.input_frame(b, 'w', {'seq': 3, 'taps': 5}, 4)
        self.advance(b, 22.99)
        self.assertIsNone(b['outcome'])
        self.advance(b, 23)
        self.assertEqual(b['outcome'], 'attacker')
        tie = self.game('mashing-battle')
        self.advance(tie, 23)
        self.assertEqual(tie['outcome'], 'tie')

    def test_advantage_is_a_lead_and_memory_targets_are_correct(self):
        for game in ('mashing-battle', 'timing-battle'):
            self.assertEqual(self.game(game, 'attacker')['position'], 5)
            self.assertEqual(self.game(game, 'defender')['position'], 3)
        self.assertEqual(self.game('memory-match', 'attacker')['targets'], {'w': 3, 'b': 4})
        self.assertEqual(self.game('memory-match', 'defender')['targets'], {'w': 4, 'b': 3})

    def test_timing_hides_future_cue_and_penalizes_early_press_once(self):
        b = self.game('timing-battle')
        state = games.public(b, 'w')
        self.assertNotIn('cueAt', state)
        self.assertIsNone(state['cue'])
        games.input_frame(b, 'w', {'seq': 1, 'press': True, 'round': b['round']}, 3.1)
        games.input_frame(b, 'w', {'seq': 2, 'press': True, 'round': b['round']}, 3.2)
        self.advance(b, b['cueAt'] + 3)
        self.assertEqual(b['position'], 3)
        self.assertEqual(b['reactions']['w'], -1)

    def test_timing_uses_server_reaction_and_ignores_stale_round(self):
        b = self.game('timing-battle')
        signal = b['cueAt']
        self.advance(b, signal)
        games.signal_seen(b, 'w', signal)
        games.signal_seen(b, 'b', signal + .1)
        games.input_frame(b, 'w', {'seq': 1, 'press': True, 'round': b['round'] - 1, 'cue': b['cue']}, signal + .1)
        self.assertNotIn('w', b['reactions'])
        games.input_frame(b, 'w', {'seq': 2, 'press': True, 'round': b['round'], 'cue': b['cue'], 'reactionMs': 0}, signal + .2)
        games.input_frame(b, 'b', {'seq': 1, 'press': True, 'round': b['round'], 'cue': b['cue']}, signal + .4)
        self.assertEqual(b['reactions'], {'w': 200, 'b': 300})
        self.assertEqual(b['position'], 5)
        b['position'] = 7
        self.advance(b, b['nextRoundAt'])
        self.advance(b, b['cueAt'])
        games.signal_seen(b, 'w', b['cueAt'])
        games.input_frame(b, 'w', {'seq': 3, 'press': True, 'round': b['round'], 'cue': b['cue']}, b['cueAt'] + .2)
        self.advance(b, b['cueAt'] + 3)
        self.assertEqual(b['outcome'], 'attacker')

    def test_dodging_server_movement_bounds_and_stuck_key_expiry(self):
        b = self.game('dodging-battle')
        games.input_frame(b, 'w', {'seq': 1, 'keys': 9, 'x': 399, 'y': 399}, 3)
        self.advance(b, 3.2)
        self.assertGreater(b['actors']['w']['x'], 140)
        self.assertLess(b['actors']['w']['x'], 150)
        self.assertEqual(b['actors']['b']['x'], 280)
        self.advance(b, 4.4)
        x = b['actors']['w']['x']
        self.advance(b, 4.7)
        self.assertEqual(b['actors']['w']['x'], x)
        self.assertEqual(games.public(b, 'b')['directions']['w'], 0)
        b['actors']['w']['x'] = 383
        games.input_frame(b, 'w', {'seq': 2, 'keys': 8}, 4.7)
        self.advance(b, 4.9)
        self.assertEqual(b['actors']['w']['x'], 384)

    def test_dodging_held_movement_survives_slow_control_round_trips(self):
        b = self.game('dodging-battle')
        b['actors']['w']['x'] = 16
        b['spawnTimer'] = -100
        for seq, now in enumerate([3, 3.65, 4.3], start=1):
            self.advance(b, now)
            games.input_frame(b, 'w', {'seq': seq, 'keys': 8}, now)
        self.advance(b, 4.6)
        self.assertAlmostEqual(b['actors']['w']['x'], 16 + 180 * 1.6, delta=4)
        self.assertEqual(games.public(b, 'b')['directions']['w'], 8)
        games.input_frame(b, 'w', {'seq': 4, 'keys': 0}, 4.6)
        self.advance(b, 4.8)
        self.assertEqual(games.public(b, 'b')['directions']['w'], 0)

    def test_timing_resume_restarts_unfinished_cue_without_changing_score(self):
        b = self.game('timing-battle')
        self.advance(b, b['cueAt'])
        original_round = b['round']
        b.update(phase='paused', pausedAt=b['cueAt'], startReady=[])
        b['reactions']['w'] = 200
        games.ready(b, 'w', 50)
        games.ready(b, 'b', 50)
        self.assertEqual(b['round'], original_round + 1)
        self.assertEqual(b['reactions'], {})
        self.assertEqual(b['position'], 4)
        self.assertIsNone(b['cue'])
        self.assertGreater(b['cueAt'], b['startAt'])

    def test_dodging_projectiles_extra_life_and_simultaneous_knockout(self):
        b = self.game('dodging-battle', 'attacker')
        b['projectiles'] = [dict(x=120, y=200, vx=0, vy=0)]
        self.advance(b, 3.03)
        self.assertEqual(b['actors']['w']['lives'], 1)
        self.assertEqual(b['phase'], 'countdown')
        self.assertEqual(b['projectiles'], [])
        resume = b['startAt']
        self.advance(b, resume + .01)
        b['projectiles'] = [dict(x=280, y=200, vx=0, vy=0)]
        self.advance(b, resume + .05)
        self.assertEqual(b['outcome'], 'attacker')
        tie = self.game('dodging-battle')
        tie['projectiles'] = [dict(x=x, y=200, vx=0, vy=0) for x in (120, 280)]
        self.advance(tie, 3.03)
        self.assertEqual(tie['outcome'], 'tie')
        spawn = self.game('dodging-battle')
        self.advance(spawn, 6)
        self.assertGreater(len(spawn['projectiles']), 0)


if __name__ == '__main__':
    unittest.main()
