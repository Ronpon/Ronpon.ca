"""Private Werblers rooms: auth, persistence, decisions, concurrency and AI."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from flask import Flask, jsonify
from models import db
from security import csrf_token, validate_csrf
from werblers_engine.mystery import MysteryEvent
from werblers_engine.types import Consumable, Curse, EquipSlot, Item, Minion, TileType, Trait
from werblers_engine.save_load import serialize_game, deserialize_game
from werblers_web import rooms
from werblers_web.routes.game_routes import game_bp
from werblers_web.routes.combat_routes import combat_bp
from werblers_web.routes.inventory_routes import inventory_bp
from werblers_web.routes.mystery_routes import mystery_bp
from werblers_web.routes.room_routes import room_bp


def make_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='werblers-online-tests', RATE_LIMIT_ENABLED=False)
    app.before_request(validate_csrf)
    app.add_url_rule('/csrf', view_func=lambda: jsonify(token=csrf_token()))
    for bp in (game_bp, combat_bp, inventory_bp, mystery_bp):
        app.register_blueprint(bp, url_prefix='/games/werblers')
    app.register_blueprint(room_bp, url_prefix='/games/werblers/api')
    return app


class OnlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='werblers-online-')
        self.patches = [patch.object(db, '_SQLITE_PATH', str(Path(self.tmp.name)/'rooms.db')),
                        patch.object(db, 'DATABASE_URL', None)]
        for p in self.patches: p.start()
        rooms.init_tables()
        self.app = make_app()
        self.clients = [self.app.test_client() for _ in range(5)]
        self.csrf = [c.get('/csrf').json['token'] for c in self.clients]
        self.tokens = [''] * 5
        self.room = None

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def post(self, pid, path, data, csrf=True):
        headers = {'X-Werblers-Token': self.tokens[pid]}
        if csrf: headers['X-CSRF-Token'] = self.csrf[pid]
        return self.clients[pid].post('/games/werblers/api'+path, json=data, headers=headers)

    def get(self, pid=0):
        response = self.clients[pid].get('/games/werblers/api/rooms/'+self.code,
                                        headers={'X-Werblers-Token': self.tokens[pid]})
        if response.status_code == 200: self.room = response.json['room']
        return response

    def create(self, mode='live'):
        response = self.post(0, '/rooms', {'name':'Host', 'mode':mode})
        self.assertEqual(response.status_code, 201, response.text)
        self.room = response.json['room']; self.code = self.room['code']; self.tokens[0] = response.json['token']

    def join(self, pid):
        response = self.post(pid, f'/rooms/{self.code}/join', {'name':f'Guest {pid}'})
        self.assertEqual(response.status_code, 200, response.text)
        self.room = response.json['room']; self.tokens[pid] = response.json['token']

    def act(self, pid, kind, expected=200, **body):
        data = {'_version':self.room['version'], '_request_id':uuid.uuid4().hex, **body}
        response = self.post(pid, f'/rooms/{self.code}/actions/{kind}', data)
        self.assertEqual(response.status_code, expected, response.text)
        if response.status_code == 200: self.room = response.json['room']
        return response

    def start(self, mode='live', count=2):
        self.create(mode)
        for pid in range(1,count): self.join(pid)
        for pid, hero in enumerate(['GREGORY','BRUNHILDE','RIZZT','BILLFOLD'][:count]): self.act(pid,'hero',hero=hero)
        self.act(0,'start')

    def seed(self, callback):
        with rooms.locked_room(self.code) as (_, room):
            state = rooms.load_state(room)
            callback(state['game'], room)
            rooms.store_state(room,state)
            room['version'] += 1
        self.get()

    def fixed_move(self, tile=TileType.BLANK):
        def setup(game, room):
            game.current_player.position=1
            game.current_player.movement_hand=[1]
            game.board[2].tile_type=tile
        self.seed(setup)

    def test_guest_lobby_private_access_capacity_and_host_start(self):
        self.create()
        self.assertEqual(self.get(1).status_code,403)
        for i in range(1,4): self.join(i)
        self.assertEqual(self.post(4,f'/rooms/{self.code}/join',{'name':'Fifth'}).status_code,409)
        self.act(0,'hero',hero='GREGORY')
        self.act(1,'hero',hero='GREGORY',expected=409)
        self.act(1,'start',expected=403)
        self.act(0,'start',expected=400)
        for pid,hero in enumerate(['BRUNHILDE','RIZZT','BILLFOLD'],1): self.act(pid,'hero',hero=hero)
        self.act(0,'start')
        self.assertEqual(self.room['phase'],'playing')
        self.assertEqual(len(self.room['state']['players']),4)
        self.assertTrue(all('token' not in s for s in self.room['seats']))
        for token in self.tokens[:4]:
            self.assertNotIn(token,json.dumps(self.room))
        self.assertNotIn('movement_deck_cards',json.dumps(self.room))

    def test_csrf_is_required(self):
        self.assertEqual(self.post(0,'/rooms',{'name':'Host','mode':'live'},csrf=False).status_code,400)
        self.start()
        response=self.post(0,f'/rooms/{self.code}/actions/pause',{'_version':self.room['version'],'_request_id':uuid.uuid4().hex},csrf=False)
        self.assertEqual(response.status_code,400)

    def test_only_current_actor_can_move_and_hands_are_private(self):
        self.start(); self.fixed_move()
        self.assertEqual(self.room['state']['players'][1]['movement_hand'],[])
        self.act(1,'begin_move',card_index=0,expected=403)
        self.act(0,'begin_move',card_index=0)
        self.assertEqual(self.room['decision']['player_id'],1)
        self.get(1)
        self.assertTrue(self.room['state']['players'][1]['movement_hand'])
        self.assertEqual(self.room['state']['players'][0]['movement_hand'],[])
        self.act(0,'begin_move',card_index=0,expected=403)

    def test_duplicate_and_stale_requests_cannot_repeat_a_turn(self):
        self.start(); self.fixed_move()
        data={'_version':self.room['version'],'_request_id':uuid.uuid4().hex,'card_index':0}
        path=f'/rooms/{self.code}/actions/begin_move'
        first=self.post(0,path,data)
        second=self.post(0,path,data)
        self.assertEqual(first.status_code,200);self.assertEqual(second.status_code,200)
        self.assertEqual(first.json['room']['version'],second.json['room']['version'])
        data['_request_id']=uuid.uuid4().hex
        self.assertEqual(self.post(1,path,data).status_code,409)

    def test_concurrent_moves_commit_only_once(self):
        self.start();self.fixed_move()
        version=self.room['version']
        def move(_):
            with self.app.test_request_context():
                try:
                    rooms.action(self.code,self.tokens[0],'begin_move',{'_version':version,'_request_id':uuid.uuid4().hex,'card_index':0})
                    return 200
                except rooms.RoomError as e: return e.status
        with ThreadPoolExecutor(max_workers=2) as pool: result=sorted(pool.map(move,range(2)))
        self.assertEqual(result,[200,409])
        self.get();self.assertEqual(self.room['state']['turn_number'],1)

    def test_async_reconnect_after_days_and_worker_restart(self):
        self.start('async');self.fixed_move(TileType.CHEST);self.act(0,'begin_move',card_index=0)
        before=self.room['decision']
        with rooms.locked_room(self.code) as (_,room):
            for s in room['seats']: s['seen']=time.time()-7*86400
        restarted=make_app().test_client()
        response=restarted.get('/games/werblers/api/rooms/'+self.code,headers={'X-Werblers-Token':self.tokens[0]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['room']['decision'],before)
        self.assertEqual(response.json['room']['mode'],'async')

    def test_disconnect_waits_and_host_can_skip_or_replace(self):
        self.start();self.fixed_move();self.act(0,'begin_move',card_index=0)
        with rooms.locked_room(self.code) as (_,room):room['seats'][1]['seen']=0
        self.get();self.assertTrue(self.room['waiting_for_connection'])
        self.act(1,'skip',player_id=0,expected=403)
        self.act(0,'skip',player_id=1)
        self.assertEqual(self.room['decision']['player_id'],0)
        self.act(0,'ai',player_id=1)
        self.assertTrue(self.room['seats'][1]['ai'])
        self.act(0,'human',player_id=1)
        self.assertFalse(self.room['seats'][1]['ai'])

    def test_host_can_pause_and_skip_pending_fight(self):
        self.start();self.fixed_move(TileType.MONSTER);self.act(0,'begin_move',card_index=0)
        self.assertEqual(self.room['decision']['phase'],'combat')
        self.act(0,'pause');self.act(0,'fight',expected=409)
        self.act(0,'skip',player_id=0)
        self.act(0,'resume')
        self.assertEqual(self.room['decision']['phase'],'move')
        self.assertEqual(self.room['decision']['player_id'],1)

    def test_me_too_belongs_to_the_opponent(self):
        self.start()
        def setup(game,room):
            game.player.traits.append(Trait('Eight Lives',effect_id='eight_lives'))
            game.player.curses.append(Curse('Source'))
            game.players[1].traits.append(Trait('Me Too!',effect_id='me_too'))
            game.players[1].curses.append(Curse('Other'))
        self.seed(setup);self.act(0,'use_eight_lives',curse_index=0)
        self.assertEqual(self.room['decision']['phase'],'me_too')
        cid=self.room['decision']['choice']['id']
        self.act(0,'resolve_me_too',choice_id=cid,curse_index=0,expected=403)
        self.act(1,'resolve_me_too',choice_id=cid,curse_index=0)
        self.assertEqual(self.room['state']['players'][1]['curses'],[])
        self.assertEqual(self.room['decision']['player_id'],0)

    def test_bystander_response_blocks_fighter_and_cannot_be_forged(self):
        self.start();self.fixed_move(TileType.MONSTER)
        self.seed(lambda game,room:game.players[1].consumables.append(Consumable('Vial',effect_id='monster_str_mod',effect_value=2)))
        self.act(0,'begin_move',card_index=0)
        self.assertEqual(self.room['decision']['phase'],'bystander')
        self.act(0,'fight',expected=403)
        self.act(0,'bystander_consumable',player_id=1,skip=True,expected=403)
        self.act(1,'bystander_consumable',player_id=0,skip=True,expected=403)
        self.act(1,'bystander_consumable',player_id=1,skip=True)
        self.assertEqual(self.room['decision']['phase'],'combat')
        self.act(0,'fight')

    def test_rewards_stay_with_owner_after_turn_advances(self):
        self.start()
        def setup(game,room):
            game.player.pending_trait_items.append(Item('Reward',EquipSlot.HELMET))
            game._current_player_idx=1
        self.seed(setup)
        self.assertEqual(self.room['decision']['player_id'],0)
        self.act(1,'place_trait_item',player_id=0,placement_choices={'placement':'pack'},expected=403)
        self.act(0,'place_trait_item',player_id=1,placement_choices={'placement':'pack'},expected=403)
        self.act(0,'place_trait_item',player_id=0,placement_choices={'placement':'pack'})
        self.assertEqual(self.room['state']['players'][0]['pack'][0]['name'],'Reward')
        self.assertEqual(self.room['decision']['player_id'],1)

    def test_pending_mystery_persists(self):
        self.start()
        self.fixed_move(TileType.MYSTERY);self.act(0,'begin_move',card_index=0)
        self.assertEqual(self.room['decision']['phase'],'mystery')
        self.get();self.act(0,'resolve_mystery',action='skip')
        self.assertEqual(self.room['decision']['player_id'],1)

    def test_failed_action_rolls_back_consumed_item(self):
        self.start()
        self.seed(lambda game,room:game.player.consumables.append(Consumable('Potion',strength_bonus=5)))
        before=self.room['state']['players'][0]['consumables']
        self.act(0,'use_consumable',consumable_index=0,expected=400)
        self.get();self.assertEqual(self.room['state']['players'][0]['consumables'],before)

    def test_ai_can_take_over_mid_fight_and_relinquish_control(self):
        self.start();self.fixed_move(TileType.MONSTER);self.act(0,'begin_move',card_index=0)
        self.act(0,'ai',player_id=0)
        self.get(1)
        self.assertEqual(self.room['decision']['player_id'],1)
        self.assertFalse(self.room['paused'])
        self.act(0,'human',player_id=0)
        self.assertFalse(self.room['seats'][0]['ai'])

    def test_ai_handles_rewards_mysteries_and_reactions(self):
        self.start()
        self.act(0,'ai',player_id=1)
        def setup(game,room):
            game.players[1].pending_trait_items.append(Item('Helmet',EquipSlot.HELMET,strength_bonus=4))
            game.players[1].pending_trait_minions.append(Minion('Friend',strength_bonus=3))
        self.seed(setup)  # poll runs computer decisions, then waits for the human
        self.assertEqual(self.room['decision']['player_id'],0)
        self.assertEqual(self.room['state']['players'][1]['helmets'][0]['name'],'Helmet')
        self.assertFalse(self.room['paused'])

    def test_combat_preview_updates_after_potion_and_reload(self):
        self.start();self.fixed_move(TileType.MONSTER)
        self.seed(lambda game,room:game.player.consumables.append(Consumable('Potion',strength_bonus=5)))
        self.act(0,'begin_move',card_index=0)
        before=self.room['decision']['combat']['player_strength']
        self.act(0,'use_consumable',consumable_index=0)
        self.get()
        self.assertEqual(self.room['decision']['combat']['player_strength'],before+5)

    def test_fair_exchange_cannot_remove_cursed_or_duplicate_equipment(self):
        self.start();self.fixed_move(TileType.MONSTER)
        def setup(game,room):
            game.player.helmets.append(Item('Bound helmet',EquipSlot.HELMET,locked_by_curse_id='bound'))
            game.player.curses.append(Curse('Bound',effect_id='bound'))
        self.seed(setup);self.act(0,'begin_move',card_index=0)
        source={'source':'equip_helmet','index':0}
        self.act(0,'crossroads_discard',equip_sources=[source],expected=400)
        self.get()
        self.assertEqual(self.room['state']['players'][0]['helmets'][0]['name'],'Bound helmet')
        self.seed(lambda game,room:game.player.curses.clear())
        self.act(0,'crossroads_discard',equip_sources=[source,source],expected=400)

    def test_simultaneous_lobby_choices_keep_both_heroes(self):
        self.create();self.join(1)
        version=self.room['version']
        self.act(0,'hero',hero='GREGORY')
        self.act(1,'hero',hero='BRUNHILDE',_version=version)
        self.assertEqual([s['hero'] for s in self.room['seats']],['GREGORY','BRUNHILDE'])
        self.act(1,'hero',hero='GREGORY',_version=version,expected=409)

    def test_host_can_interrupt_ai_despite_stale_revision(self):
        self.start();self.fixed_move()
        version=self.room['version']
        self.act(0,'ai',player_id=0)
        self.get(1)
        self.act(0,'pause',_version=version)
        self.assertTrue(self.room['paused'])
        self.act(0,'human',player_id=0,_version=version)
        self.assertFalse(self.room['seats'][0]['ai'])
        self.act(1,'human',player_id=1,expected=403)
        self.act(0,'skip',player_id=1,_version=version,expected=409)

    def test_future_skip_waits_for_the_target_turn(self):
        self.start();self.fixed_move()
        self.act(0,'skip',player_id=1)
        self.assertTrue(self.room['seats'][1]['skip_next'])
        self.assertEqual(self.room['decision']['player_id'],0)
        self.act(0,'begin_move',card_index=0)
        self.get()
        self.assertFalse(self.room['seats'][1]['skip_next'])
        self.assertEqual(self.room['decision']['player_id'],0)

    def test_invalid_ability_and_phase_bypass_are_rejected(self):
        self.start();self.fixed_move(TileType.CHEST)
        self.act(0,'begin_move',card_index=0,activated={'touchdown':True},expected=400)
        self.act(0,'begin_move',card_index=0)
        self.act(0,'begin_move',card_index=0,expected=409)
        self.act(0,'fight',expected=409)
        self.act(0,'play_turn',expected=409)

    def test_johnil_loss_choice_belongs_to_fighter_and_survives_reconnect(self):
        from test_werblers_review import johnil_game
        self.start()
        with rooms.locked_room(self.code) as (_, room):
            state = rooms.load_state(room)
            state['game'] = johnil_game()
            rooms.store_state(room, state)
            room['version'] += 1
        self.get()
        self.act(0, 'fight')
        choice = self.room['decision']['choice']
        self.assertEqual(self.room['decision']['phase'], 'trait_loss')
        self.get(1)
        self.assertEqual(self.room['decision']['choice'], choice)
        self.act(1, 'resolve_trait_loss', choice_id=choice['id'], trait_indices=[1,2], expected=403)
        self.act(0, 'resolve_trait_loss', choice_id=choice['id'], trait_indices=[1,2])
        self.assertEqual([t['name'] for t in self.room['state']['players'][0]['traits']], ['Keep'])
        self.assertEqual(self.room['decision']['player_id'], 1)

    def test_ai_finishes_a_pending_johnil_choice(self):
        from test_werblers_review import johnil_game
        self.start()
        with rooms.locked_room(self.code) as (_, room):
            state = rooms.load_state(room)
            game = johnil_game()
            game.fight()
            state['game'] = game
            rooms.store_state(room, state)
            room['version'] += 1
        self.get()
        self.act(0, 'ai', player_id=0)
        self.get(1)
        self.assertFalse(self.room['paused'])
        self.assertEqual(len(self.room['state']['players'][0]['traits']), 1)
        self.assertEqual(self.room['decision']['player_id'], 1)

    def test_shop_scavenger_uses_selected_item_once(self):
        self.start()
        self.fixed_move(TileType.SHOP)
        self.seed(lambda game,room: game.player.traits.append(Trait('Scavenger',effect_id='scavenger')))
        self.act(0, 'begin_move', card_index=0)
        before = self.room['decision']['items']
        self.assertTrue(self.room['decision']['scavenger'])
        self.act(0, 'scavenger_swap', item_index=1)
        after = self.room['decision']['items']
        self.assertEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])
        self.assertFalse(self.room['decision']['scavenger'])
        self.act(0, 'scavenger_swap', item_index=0, expected=400)


if __name__=='__main__':unittest.main()
