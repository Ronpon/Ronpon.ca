"""Regression coverage for decision recovery, boss choices and shared rules."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from flask import Flask

from werblers_engine import content as C
from werblers_engine.deck import Deck
from werblers_engine.game import Game
from werblers_engine.heroes import HeroId
from werblers_engine.mystery import MysteryEvent
from werblers_engine.save_load import serialize_game, deserialize_game
from werblers_engine.types import Curse, EquipSlot, Item, Monster, TileType, Trait
from werblers_web.decisions import interaction
from werblers_web.routes import helpers
from werblers_web.routes.game_routes import game_bp
from werblers_web.routes.combat_routes import combat_bp
from werblers_web.routes.inventory_routes import inventory_bp
from werblers_web.routes.mystery_routes import mystery_bp
from werblers_web.routes.save_routes import save_bp


def land(game, tile, position=2):
    game.current_player.position = position - 1
    game.current_player.movement_hand = [1]
    game.board[position].tile_type = tile
    return game.begin_move()


def johnil_game():
    game = Game(num_players=2, seed=1)
    game.player.traits = [Trait('Keep'), Trait('Lose A'), Trait('Lose B')]
    game.player.miniboss1_defeated = game.player.miniboss2_defeated = True
    game.player_werblers[0] = next(deepcopy(b) for b in C.WERBLER_POOL if b.effect_id == 'johnil')
    land(game, TileType.WERBLER, 90)
    return game


class EngineReviewTests(unittest.TestCase):
    def test_touchdown_uses_the_interactive_boss_and_loss_choice(self):
        game = johnil_game()
        game._pending_combat = None
        game.player.position = 65
        game.player.traits.append(Trait('Touchdown!', effect_id='touchdown'))
        self.assertEqual(game.begin_move(activated={'touchdown':True})['phase'], 'combat')
        self.assertEqual(game.fight()['phase'], 'trait_loss')

    def test_johnil_choice_survives_save_and_finishes_exactly_once(self):
        game = johnil_game()
        result = game.fight()
        self.assertEqual(result['phase'], 'trait_loss')
        self.assertEqual(len(game.player.traits), 3)
        self.assertEqual(game.current_player.player_id, 0)
        self.assertEqual(game.player.position, 61)
        game = deserialize_game(serialize_game(game))
        choice = interaction(game)['choice']
        for indices in ([1, 1], [1], [1, 99], [True, 2], None):
            before = serialize_game(game)
            with self.assertRaises(ValueError):
                game.resolve_trait_loss(choice['id'], indices)
            self.assertEqual(serialize_game(game), before)
        game.resolve_trait_loss(choice['id'], [1, 2])
        self.assertEqual([t.name for t in game.players[0].traits], ['Keep'])
        self.assertEqual(game.current_player.player_id, 1)
        with self.assertRaises(ValueError):
            game.resolve_trait_loss(choice['id'], [0, 1])

    def test_failed_fight_restores_state_and_remains_retryable(self):
        game = johnil_game()
        before = serialize_game(game)
        with patch('werblers_engine.werbler._apply_werbler_loss', side_effect=RuntimeError('probe')):
            with self.assertRaises(RuntimeError):
                game.fight()
        self.assertEqual(serialize_game(game), before)
        self.assertEqual(game.fight()['phase'], 'trait_loss')

    def test_legacy_johnil_selection_obeys_index_callback_contract(self):
        game = johnil_game()
        from werblers_engine.werbler import _apply_werbler_loss
        _apply_werbler_loss(game.player, game.player_werblers[0], [], select_fn=game._select)
        self.assertEqual(len(game.player.traits), 1)

    def test_night_preview_and_result_match_actual_winning_strength(self):
        game = Game(hero_ids=[HeroId.RIZZT], seed=1)
        game.is_night = True
        game.monster_decks[1] = Deck([Monster('Night probe', strength=8, level=1)], 1)
        preview = land(game, TileType.MONSTER)['combat_info']
        self.assertEqual(preview['player_strength'], 10)
        result = game.fight()
        self.assertEqual(result['combat_result'], 'WIN')
        self.assertEqual(result['combat_info']['player_strength'], 10)

    def test_boss_result_keeps_prefight_bonuses_and_recomputed_equipment(self):
        game = Game(hero_ids=[HeroId.RIZZT], seed=1)
        game.is_night = True
        game.active_miniboss_t2 = next(deepcopy(b) for b in C.MINIBOSS_POOL_T2 if b.effect_id == 'crossroads_demon')
        game.player.miniboss1_defeated = True
        land(game, TileType.MINIBOSS, 60)
        game.player.helmets.append(Item('Helmet', EquipSlot.HELMET, strength_bonus=5))
        game._prefight_str_bonus = 12
        game._prefight_monster_str_bonus = -2
        preview = game.combat_preview()
        self.assertEqual(preview['player_strength'], 27)
        self.assertEqual(preview['monster_strength'], 21)
        result = game.fight()
        self.assertEqual(result['combat_result'], 'WIN')
        for key in ('player_strength', 'monster_strength'):
            self.assertEqual(result['combat_info'][key], preview[key])

    def test_monster_debuff_clamps_before_its_bonus_against_male_heroes(self):
        game = Game(hero_ids=[HeroId.RIZZT], seed=1)
        game.monster_decks[1] = Deck([Monster('Probe',strength=4,level=1,bonus_vs_male=3)],1)
        land(game, TileType.MONSTER)
        game._prefight_monster_str_bonus = -10
        preview = game.combat_preview()
        self.assertEqual(preview['monster_strength'], 3)
        self.assertEqual(game.fight()['combat_info']['monster_strength'], preview['monster_strength'])

    def test_scavenger_replaces_selected_item_once_in_chest_and_shop(self):
        for tile in (TileType.CHEST, TileType.SHOP):
            with self.subTest(tile=tile):
                game = Game(seed=1)
                game.player.traits.append(Trait('Scavenger', effect_id='scavenger'))
                land(game, tile)
                old = list(game._pending_offer['items'])
                index = len(old) - 1
                game.scavenger_swap(index)
                self.assertNotEqual(game._pending_offer['items'][index].name, old[index].name)
                self.assertEqual(game._pending_offer['items'][:index], old[:index])
                game = deserialize_game(serialize_game(game))
                before = serialize_game(game)
                with self.assertRaises(ValueError):
                    game.scavenger_swap(index)
                self.assertEqual(serialize_game(game), before)

    def test_old_save_without_trait_loss_fields_still_loads(self):
        data = json.loads(serialize_game(Game(seed=1)))
        data.pop('_pending_trait_loss')
        data.pop('_next_trait_loss_id')
        loaded = deserialize_game(json.dumps(data))
        self.assertIsNone(loaded._pending_trait_loss)
        self.assertEqual(loaded._next_trait_loss_id, 1)


class ApiReviewTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='review-tests', RATE_LIMIT_ENABLED=False)
        for bp in (game_bp, combat_bp, inventory_bp, mystery_bp, save_bp):
            self.app.register_blueprint(bp, url_prefix='/games/werblers')
        self.client = self.app.test_client()
        self.ids = []
        self.set_game(Game(num_players=2, seed=1))

    def tearDown(self):
        for sid in self.ids:
            helpers._sessions.pop(sid, None)

    def set_game(self, game):
        self.client.post('/games/werblers/api/new_game', json={'seed': 1})
        with self.client.session_transaction() as session:
            self.sid = session['game_id']
        self.ids.append(self.sid)
        helpers._sessions[self.sid]['game'] = game
        self.game = game

    def post(self, action, **body):
        return self.client.post('/games/werblers/api/' + action, json=body)

    def load_game(self, game):
        with patch('werblers_web.routes.save_routes._authorized_profile', return_value=True), \
             patch('werblers_web.routes.save_routes.db.load_save', return_value=serialize_game(game)):
            response = self.post('load', profile_id=1, slot_number=1)
        with self.client.session_transaction() as session:
            self.ids.append(session['game_id'])
        self.assertEqual(response.status_code, 200)
        return response.json

    def test_chest_and_shop_load_restore_offer_and_can_complete(self):
        for tile in (TileType.CHEST, TileType.SHOP):
            game = Game(num_players=2, seed=2)
            game.player.traits.append(Trait('Scavenger', effect_id='scavenger'))
            land(game, tile)
            data = self.load_game(game)
            self.assertEqual(data['resume']['phase'], tile.name.lower())
            self.assertTrue(data['resume']['items'][0]['card_image'])
            self.assertTrue(data['resume']['scavenger'])
            self.assertEqual(self.post('begin_move', card_index=0).status_code, 409)
            self.assertEqual(self.post('resolve_offer', take=False).status_code, 200)
            self.assertEqual(self.post('begin_move', card_index=0).status_code, 200)

    def test_load_reconstructs_mystery_rake_fairy_item_and_minion_decisions(self):
        from werblers_engine.types import Minion
        cases = [
            ('mystery', {'type':'mystery', 'event':MysteryEvent('the_wheel','The Wheel',1,'Spin'), 'level':1}),
            ('rake_it_in', {'type':'rake_it_in', 'sub_type':'shop', 'shop_remaining':[Item('Bonus',EquipSlot.HELMET)]}),
            ('fairy_king_reward', {'type':'fairy_king_reward', 'reward_items':[Item('Prize',EquipSlot.HELMET)]}),
        ]
        for phase, offer in cases:
            game = Game(seed=1)
            game._pending_offer = offer
            data = self.load_game(game)
            self.assertEqual(data['resume']['phase'], phase)
            self.assertIn('event' if phase == 'mystery' else 'items', data['resume'])
        for phase in ('item', 'minion'):
            game = Game(num_players=2, seed=1)
            game._current_player_idx = 1
            if phase == 'item':
                game.players[0].pending_trait_items.append(Item('Reward',EquipSlot.HELMET))
            else:
                game.players[0].pending_trait_minions.append(Minion('Friend',strength_bonus=2))
            data = self.load_game(game)
            self.assertEqual((data['resume']['phase'], data['resume']['player_id']), (phase,0))

    def test_trait_choice_blocks_other_actions_and_loads_with_same_id(self):
        game = johnil_game()
        self.set_game(game)
        response = self.post('fight')
        self.assertEqual(response.json['phase'], 'trait_loss')
        choice = response.json['state']['pending_trait_loss']
        for action in ('begin_move', 'use_mages_gauntlet', 'resolve_offer'):
            self.assertEqual(self.post(action).status_code, 409)
        data = self.load_game(game)
        self.assertEqual(data['resume']['choice']['id'], choice['id'])
        response = self.post('resolve_trait_loss', choice_id=choice['id'], trait_indices=[1,2])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['state']['current_player_id'], 1)

    def test_fair_exchange_is_atomic_and_rejects_cursed_or_duplicate_items(self):
        game = self.game
        game.active_miniboss_t2 = next(deepcopy(b) for b in C.MINIBOSS_POOL_T2 if b.effect_id == 'crossroads_demon')
        game.player.miniboss1_defeated = True
        game.player.helmets = [Item('Locked',EquipSlot.HELMET,locked_by_curse_id='lock')]
        game.player.weapons = [Item('Free',EquipSlot.WEAPON)]
        game.player.curses = [Curse('Lock',effect_id='lock')]
        land(game, TileType.MINIBOSS, 60)
        weapon = {'source':'equip_weapon','index':0}
        for sources in ([weapon, {'source':'equip_helmet','index':0}], [weapon, weapon]):
            before = serialize_game(game)
            response = self.post('crossroads_discard', equip_sources=sources)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(serialize_game(game), before)
        self.assertEqual(self.post('crossroads_discard', equip_sources=[weapon]).status_code, 200)
        self.assertEqual(len(game.player.weapons), 0)
        self.assertEqual(len(game.player.helmets), 1)


if __name__ == '__main__':
    unittest.main()
