"""Werblers logic regressions; uses in-memory games and mocked save storage.

Run: python -B -m unittest discover -s tests -p test_werblers_logic.py
"""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from flask import Flask

from werblers_engine import content as C
from werblers_engine.game import Game
from werblers_engine.heroes import HEROES, HeroId
from werblers_engine.save_load import serialize_game, deserialize_game
from werblers_engine.types import Curse, EquipSlot, Item, TileType, Trait
from werblers_engine.werbler import _apply_werbler_loss
from werblers_web.routes import helpers
from werblers_web.routes.game_routes import game_bp
from werblers_web.routes.combat_routes import combat_bp
from werblers_web.routes.inventory_routes import inventory_bp
from werblers_web.routes.save_routes import save_bp


def land(game, tile_type, position=2):
    player = game.current_player
    player.position = position - 1
    player.movement_hand = [1]
    game.board[position].tile_type = tile_type
    return game.begin_move()


def locked_inventory(game, weapon=False):
    player = game.current_player
    slot = EquipSlot.WEAPON if weapon else EquipSlot.HELMET
    locked = Item('Locked item', slot, locked_by_curse_id='test_lock')
    player._slot_list(slot).append(locked)
    player.curses.append(Curse('Lock', effect_id='test_lock'))
    return locked


class EngineTests(unittest.TestCase):
    def test_games_and_content_templates_are_independent(self):
        first, second = Game(seed=1), Game(seed=1)
        for name in ('monster_decks', 'item_decks'):
            for level, deck in getattr(first, name).items():
                other = getattr(second, name)[level]
                for a, b in zip(deck._cards, other._cards):
                    self.assertEqual(a, b)
                    self.assertIsNot(a, b)
        gauntlet = next(i for i in first.item_decks[3]._cards if i.effect_id == 'mages_gauntlet')
        first.player.equip(gauntlet)
        first.player.traits.append(Trait('Sacrifice'))
        first.use_mages_gauntlet(0)
        for pool in (second.item_decks[3]._cards, C.ITEM_POOL_L3):
            self.assertEqual(next(i for i in pool if i.effect_id == 'mages_gauntlet').tokens, 0)
        for boss in first.player_werblers.values():
            boss.strength += 10
        self.assertNotEqual(first.player_werblers[0].strength, second.player_werblers[0].strength)

    def test_starting_equipment_does_not_mutate_hero_template(self):
        a = Game(hero_ids=[HeroId.RIZZT])
        b = Game(hero_ids=[HeroId.RIZZT])
        before = deepcopy(HEROES[HeroId.RIZZT].starting_items)
        a.player.weapons[0].tokens += 7
        self.assertEqual(HEROES[HeroId.RIZZT].starting_items, before)
        self.assertEqual(b.player.weapons[0].tokens, 0)

    def test_combat_save_restores_shared_deck_and_player_references(self):
        game = Game(num_players=2, seed=123)
        self.assertEqual(land(game, TileType.MONSTER)['phase'], 'combat')
        game._prefight_str_bonus = 5
        loaded = deserialize_game(serialize_game(game))
        self.assertIs(loaded._pending_combat['effective_deck'], loaded.monster_decks[1])
        self.assertIs(loaded._pending_combat['other_players'][0], loaded.players[1])
        self.assertEqual(loaded._prefight_str_bonus, 5)
        expected, actual = game.fight(), loaded.fight()
        self.assertEqual(actual['combat_result'], expected['combat_result'])
        self.assertEqual(actual['log'], expected['log'])
        self.assertIsNone(loaded._pending_combat)

    def test_loaded_monster_redraw_uses_real_deck(self):
        game = Game(seed=123)
        game.player.traits.append(Trait('Again', effect_id='ill_come_in_again'))
        land(game, TileType.MONSTER)
        loaded = deserialize_game(serialize_game(game))
        before = loaded.monster_decks[1].remaining()
        old = loaded._pending_combat['monster']
        loaded.use_ill_come_in_again()
        self.assertEqual(loaded.monster_decks[1].remaining(), before)
        self.assertIn(old, loaded.monster_decks[1]._cards)

    def test_miniboss_save_restores_active_boss_identity(self):
        game = Game(num_players=2, seed=2)
        land(game, TileType.MINIBOSS, 30)
        loaded = deserialize_game(serialize_game(game))
        self.assertIs(loaded._pending_combat['monster'], loaded.active_miniboss_t1)
        self.assertIs(loaded._pending_combat['other_players'][0], loaded.players[1])
        loaded.fight()

    def test_brady_theft_limit_survives_save_and_pending_fight(self):
        game = Game(num_players=4, seed=12)
        pid = next(pid for pid, boss in game.player_werblers.items() if boss.effect_id == 'brady')
        game._current_player_idx = pid
        player, boss = game.current_player, game.player_werblers[pid]
        for _ in range(2):
            player.helmets.append(Item('Helmet', EquipSlot.HELMET, strength_bonus=2))
            _apply_werbler_loss(player, boss, [])
        player.miniboss1_defeated = player.miniboss2_defeated = True
        land(game, TileType.WERBLER, 90)
        loaded = deserialize_game(serialize_game(game))
        restored = loaded.player_werblers[pid]
        self.assertIs(loaded._pending_combat['monster'], restored)
        self.assertEqual(restored._brady_thefts, 2)
        self.assertEqual(restored._brady_nice_hat_bonus, 4)
        helmet = Item('Third helmet', EquipSlot.HELMET, strength_bonus=2)
        loaded.current_player.helmets.append(helmet)
        loaded.fight()
        self.assertIn(helmet, loaded.players[pid].helmets)
        self.assertEqual(restored.strength, 44)

    def test_old_idle_save_loads_without_new_fields(self):
        data = json.loads(serialize_game(Game(seed=1)))
        data.pop('_pending_me_too')
        data.pop('_next_me_too_id')
        for p in data['players']:
            p.pop('_pending_curse_discards')
        for boss in data['player_werblers'].values():
            boss.pop('_brady_thefts')
            boss.pop('_brady_nice_hat_bonus')
        loaded = deserialize_game(json.dumps(data))
        self.assertIsNone(loaded.pending_me_too())
        self.assertEqual(loaded.player_werblers[0]._brady_thefts, 0)

    def test_locked_replacement_keeps_every_item_and_offer(self):
        for action in ('swap', 'discard'):
            with self.subTest(action=action):
                game = Game(seed=2)
                locked = locked_inventory(game)
                incoming = Item('Reward', EquipSlot.HELMET)
                game._pending_offer = {'type': 'chest', 'items': [incoming]}
                before = serialize_game(game)
                with self.assertRaisesRegex(ValueError, 'locked'):
                    game.resolve_offer({'take': True, 'placement': 'equip', 'equip_action': action})
                self.assertEqual(serialize_game(game), before)
                self.assertEqual(game.player.helmets, [locked])
                self.assertEqual(game.player.pack, [])

    def test_two_handed_swap_does_not_partially_remove_weapons(self):
        game = Game()
        game.player.weapons.append(Item('Free weapon', EquipSlot.WEAPON))
        locked_inventory(game, weapon=True)
        incoming = Item('Two hander', EquipSlot.WEAPON, hands=2)
        before = serialize_game(game)
        with self.assertRaisesRegex(ValueError, 'locked'):
            game._apply_item_to_player(game.player, incoming, {'placement': 'equip'}, [])
        self.assertEqual(serialize_game(game), before)

    def test_unlocked_swap_still_works(self):
        game = Game()
        locked = locked_inventory(game)
        game.player.curses.clear()
        incoming = Item('Reward', EquipSlot.HELMET)
        game._apply_item_to_player(game.player, incoming, {'placement': 'equip'}, [])
        self.assertEqual(game.player.helmets, [incoming])
        self.assertEqual(game.player.pack, [locked])

    def test_invalid_pack_replacement_leaves_inventory_unchanged(self):
        game = Game()
        game.player.pack = [Item(str(i), EquipSlot.HELMET) for i in range(3)]
        before = serialize_game(game)
        with self.assertRaises(ValueError):
            game._apply_item_to_player(game.player, Item('Reward', EquipSlot.HELMET),
                                       {'placement': 'pack', 'pack_discard_index': 99}, [])
        self.assertEqual(serialize_game(game), before)

    def test_blank_tile_does_not_trigger_me_too(self):
        game = Game(num_players=2)
        game.players[1].traits.append(Trait('Me Too!', effect_id='me_too'))
        game.players[1].curses.append(Curse('Keep me'))
        land(game, TileType.BLANK)
        self.assertEqual(len(game.players[1].curses), 1)
        self.assertIsNone(game.pending_me_too())

    def test_eight_lives_offers_choice_and_accepts_selected_curse_once(self):
        game = Game(num_players=2)
        game.player.traits.append(Trait('Eight Lives', effect_id='eight_lives'))
        game.player.curses.append(Curse('Source'))
        other = game.players[1]
        other.traits.append(Trait('Me Too!', effect_id='me_too'))
        other.curses = [Curse('Keep'), Curse('Discard')]
        game.use_eight_lives()
        choice = game.pending_me_too()
        self.assertEqual(len(other.curses), 2)
        self.assertEqual(choice['player_id'], 1)
        game = deserialize_game(serialize_game(game))
        game.resolve_me_too(choice['id'], 1)
        self.assertEqual([c.name for c in game.players[1].curses], ['Keep'])
        with self.assertRaises(ValueError):
            game.resolve_me_too(choice['id'], 0)

    def test_me_too_decline_and_invalid_choice_do_not_remove_curses(self):
        game = Game(num_players=2)
        game.players[1].traits.append(Trait('Me Too!', effect_id='me_too'))
        game.players[1].curses.append(Curse('Keep'))
        game.player.curses.append(Curse('Source'))
        game.player.discard_curse(game.player.curses[0])
        game._finish_post_encounter(game.player, [])
        choice = game.pending_me_too()
        with self.assertRaises(ValueError):
            game.resolve_me_too(choice['id'], 99)
        self.assertEqual(game.pending_me_too(), choice)
        game.resolve_me_too(choice['id'])
        self.assertIsNone(game.pending_me_too())
        self.assertEqual(len(game.players[1].curses), 1)

    def test_curse_transfer_is_not_a_discard(self):
        game = Game(num_players=2, hero_ids=[HeroId.GREGORY, HeroId.BILLFOLD])
        game.player.curses.append(Curse('Transfer'))
        game.players[1].traits.append(Trait('Me Too!', effect_id='me_too'))
        game.use_contagious_mutagen(0, 1)
        game._finish_post_encounter(game.player, [])
        self.assertIsNone(game.pending_me_too())

    def test_kneel_discard_after_loss_offers_me_too(self):
        game = Game(num_players=2, seed=1)
        game.player.miniboss1_defeated = game.player.miniboss2_defeated = True
        game.player.curses.append(Curse('KNEEL!', effect_id='kneel'))
        game.players[1].traits.append(Trait('Me Too!', effect_id='me_too'))
        game.players[1].curses.append(Curse('Other curse'))
        land(game, TileType.WERBLER, 90)
        game.fight()
        self.assertEqual(game.pending_me_too()['player_id'], 1)
        self.assertEqual(len(game.players[1].curses), 1)

    def test_me_too_discard_can_trigger_another_player(self):
        game = Game(num_players=3)
        for p in game.players:
            p.curses.append(Curse('Curse'))
        for p in game.players[1:]:
            p.traits.append(Trait('Me Too!', effect_id='me_too'))
        game.player.discard_curse(game.player.curses[0])
        game._collect_curse_discards([])
        game.resolve_me_too(game.pending_me_too()['id'], 0)
        game.resolve_me_too(game.pending_me_too()['id'])
        # Player 2 declined the first discard, but player 1's discard is a new trigger.
        self.assertEqual(game.pending_me_too()['source_player_id'], 1)
        game.resolve_me_too(game.pending_me_too()['id'], 0)
        self.assertIsNone(game.pending_me_too())

    def test_rake_it_in_rejects_locked_sacrifice_and_preserves_offer(self):
        game = Game()
        locked_inventory(game)
        game._pending_offer = {'type': 'rake_it_in', 'sub_type': 'chest', 'level': 1}
        before = serialize_game(game)
        with self.assertRaisesRegex(ValueError, 'locked'):
            game.resolve_rake_it_in(True, 'equip_helmet', 0)
        self.assertEqual(serialize_game(game), before)

    def test_rake_it_in_validates_bonus_before_spending_sacrifice(self):
        game = Game()
        locked_inventory(game)
        game.player.pack.append(Item('Sacrifice', EquipSlot.LEGS))
        game._pending_offer = {'type': 'rake_it_in', 'sub_type': 'shop', 'level': 1,
                               'shop_remaining': [Item('Reward', EquipSlot.HELMET)]}
        before = serialize_game(game)
        with self.assertRaisesRegex(ValueError, 'locked'):
            game.resolve_rake_it_in(True, 'pack', 0, 0, {'placement': 'equip'})
        self.assertEqual(serialize_game(game), before)
        result = game.resolve_rake_it_in(True, 'pack', 0, 0, {'placement': 'pack'})
        self.assertEqual(result['phase'], 'done')
        self.assertEqual([i.name for i in game.player.pack], ['Reward'])

    def test_legacy_pending_boss_is_relinked_on_load(self):
        game = Game(seed=2)
        land(game, TileType.MINIBOSS, 30)
        data = json.loads(serialize_game(game))
        data['_pending_combat']['monster'] = {'_type': 'Monster', **data['active_miniboss_t1']}
        loaded = deserialize_game(json.dumps(data))
        self.assertIs(loaded._pending_combat['monster'], loaded.active_miniboss_t1)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='werblers-test', RATE_LIMIT_ENABLED=False)
        for bp in (game_bp, combat_bp, inventory_bp, save_bp):
            self.app.register_blueprint(bp, url_prefix='/games/werblers')
        self.client = self.app.test_client()
        self.client.post('/games/werblers/api/new_game', json={'num_players': 2, 'seed': 123})
        with self.client.session_transaction() as session:
            self.sid = session['game_id']
        self.game = helpers._sessions[self.sid]['game']

    def tearDown(self):
        with self.client.session_transaction() as session:
            helpers._sessions.pop(session.get('game_id'), None)
        helpers._sessions.pop(self.sid, None)

    def post(self, endpoint, **data):
        return self.client.post('/games/werblers/api/' + endpoint, json=data)

    def test_combat_save_load_and_fight_through_api(self):
        land(self.game, TileType.MONSTER)
        with patch('werblers_web.routes.save_routes._authorized_profile', return_value=True), \
             patch('werblers_web.routes.save_routes.db.save_game', return_value={}) as save:
            response = self.post('save', profile_id=1, slot_number=1)
            self.assertEqual(response.status_code, 200)
            saved = save.call_args.kwargs['game_state_json']
        with patch('werblers_web.routes.save_routes._authorized_profile', return_value=True), \
             patch('werblers_web.routes.save_routes.db.load_save', return_value=saved):
            response = self.post('load', profile_id=1, slot_number=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['resume']['phase'], 'combat')
        self.assertIn('card_image', response.json['resume']['combat_info'])
        self.assertEqual(self.post('fight').status_code, 200)

    def test_cursed_inventory_actions_are_rejected_without_mutation(self):
        locked_inventory(self.game)
        self.game.player.pack.append(Item('Replacement', EquipSlot.HELMET))
        for endpoint, data in (
            ('equip_from_pack', {'pack_index': 0, 'to_pack': True}),
            ('equip_from_pack', {'pack_index': 0, 'force': True}),
            ('manage_item', {'source': 'equip_helmet', 'index': 0, 'action': 'to_pack', 'discard_pack_index': 0}),
            ('manage_item', {'source': 'equip_helmet', 'index': 0, 'action': 'discard'}),
        ):
            with self.subTest(endpoint=endpoint, data=data):
                before = serialize_game(self.game)
                response = self.post(endpoint, **data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(serialize_game(self.game), before)

    def test_failed_reward_placement_can_be_retried(self):
        locked_inventory(self.game)
        land(self.game, TileType.CHEST)
        self.game._pending_offer['items'] = [Item('Reward', EquipSlot.HELMET)]
        response = self.post('resolve_offer', take=True, placement='equip')
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(self.game._pending_offer)
        response = self.post('resolve_offer', take=True, placement='pack')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i.name for i in self.game.player.pack], ['Reward'])

    def test_me_too_blocks_other_actions_until_player_chooses(self):
        self.game.player.traits.append(Trait('Eight Lives', effect_id='eight_lives'))
        self.game.player.curses.append(Curse('Source'))
        self.game.players[1].traits.append(Trait('Me Too!', effect_id='me_too'))
        self.game.players[1].curses.append(Curse('Keep'))
        response = self.post('use_eight_lives', curse_index=0)
        choice = response.json['state']['pending_me_too']
        self.assertIsNotNone(choice)
        self.assertEqual(self.post('begin_move', card_index=0).status_code, 409)
        self.assertEqual(self.post('fight').status_code, 409)
        response = self.post('resolve_me_too', choice_id=choice['id'], curse_index=None)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['state']['pending_me_too'])

    def test_rejected_trait_item_remains_available(self):
        locked_inventory(self.game)
        self.game.player.pending_trait_items.append(Item('Reward', EquipSlot.HELMET))
        before = serialize_game(self.game)
        response = self.post('place_trait_item', placement_choices={'placement': 'equip'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(serialize_game(self.game), before)
        response = self.post('place_trait_item', placement_choices={'placement': 'pack'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.game.player.pending_trait_items, [])

    def test_multi_weapon_pack_swap_is_atomic_when_second_weapon_locked(self):
        self.game.player.weapons.append(Item('Free weapon', EquipSlot.WEAPON))
        locked_inventory(self.game, weapon=True)
        self.game.player.pack.append(Item('Two hander', EquipSlot.WEAPON, hands=2))
        before = serialize_game(self.game)
        response = self.post('equip_from_pack', pack_index=0,
                             displaced_actions=[{'action': 'discard'}, {'action': 'to_pack'}])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(serialize_game(self.game), before)


if __name__ == '__main__':
    unittest.main()
