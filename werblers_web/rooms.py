"""Persistent private Werblers rooms and server-authoritative action dispatch.

All room reads/mutations are serialized by a database row lock (PostgreSQL) or
BEGIN IMMEDIATE (SQLite). Guest seat secrets never appear in public snapshots.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import re
import secrets
import time

from flask import current_app, g

from models.db import get_conn, is_postgres, ph
from werblers_engine.game import Game
from werblers_engine.heroes import HeroId
from werblers_engine.save_load import serialize_game, deserialize_game
from werblers_engine.types import GameStatus
from werblers_web.serializers import build_state
from werblers_web.decisions import interaction

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
ONLINE_SECONDS = 45
HANDLERS = {
    **{a: f'game.api_{a}' for a in (
        'begin_move', 'resolve_charlie_work', 'resolve_offer', 'resolve_rake_it_in',
        'place_trait_item', 'resolve_minion', 'resolve_me_too', 'resolve_trait_loss', 'use_mages_gauntlet')},
    **{a: f'combat.api_{a}' for a in (
        'fight', 'flee', 'swiftness_flee', 'use_ill_come_in_again', 'use_eight_lives',
        'summon_monster', 'crossroads_discard', 'use_consumable', 'use_pack_consumable',
        'bystander_consumable')},
    **{a: f'inventory.api_{a}' for a in (
        'equip_from_pack', 'manage_item', 'discard_consumable', 'release_monster', 'scavenger_swap')},
    **{a: f'mystery.api_{a}' for a in ('resolve_mystery', 'resolve_fairy_king_reward')},
}
INVENTORY = {'equip_from_pack', 'manage_item', 'discard_consumable', 'release_monster'}


class RoomError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def init_tables():
    with get_conn() as conn:
        conn.cursor().execute('''CREATE TABLE IF NOT EXISTS werblers_rooms (
            code TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at DOUBLE PRECISION NOT NULL
        )''')


def normalize_code(value):
    code = value.strip().upper() if isinstance(value, str) else ''
    if not re.fullmatch(r'[A-HJ-NP-Z2-9]{6}', code):
        raise RoomError('Enter a six-character room code.')
    return code


def clean_name(value):
    if not isinstance(value, str):
        raise RoomError('Enter your name.')
    name = ' '.join(value.split())
    if not name or len(name) > 24 or any(ord(c) < 32 for c in name):
        raise RoomError('Use a name between 1 and 24 characters.')
    return name


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_seat(name, token):
    return {'name': clean_name(name), 'token': token_hash(token), 'seen': time.time(),
            'hero': None, 'ai': False, 'skip_next': False, 'requests': []}


@contextmanager
def locked_room(code):
    code = normalize_code(code)
    with get_conn() as conn:
        cur = conn.cursor()
        if not is_postgres():
            cur.execute('BEGIN IMMEDIATE')
        lock = ' FOR UPDATE' if is_postgres() else ''
        cur.execute(f'SELECT state FROM werblers_rooms WHERE code = {ph()}{lock}', (code,))
        row = cur.fetchone()
        if row is None:
            raise RoomError('Room not found. Check the invitation code.', 404)
        room = json.loads(row['state'])
        yield code, room
        cur.execute(f'UPDATE werblers_rooms SET state = {ph()}, updated_at = {ph()} WHERE code = {ph()}',
                    (json.dumps(room), time.time(), code))


def authenticate(room, token):
    if isinstance(token, str) and 20 <= len(token) <= 128:
        digest = token_hash(token)
        for pid, seat in enumerate(room['seats']):
            if hmac.compare_digest(seat['token'], digest):
                return pid
    raise RoomError('Join this room first, or use the browser where you joined.', 403)


def create(name, mode):
    if mode not in ('live', 'async'):
        raise RoomError('Choose Live or Play at your own pace.')
    token = secrets.token_urlsafe(32)
    room = {'version': 1, 'mode': mode, 'seats': [new_seat(name, token)], 'phase': 'lobby',
            'game': None, 'last_log': [], 'pending_log': [], 'notice': '', 'paused': False}
    with get_conn() as conn:
        cur = conn.cursor()
        for _ in range(12):
            code = ''.join(secrets.choice(ALPHABET) for _ in range(6))
            cur.execute(f'INSERT INTO werblers_rooms (code, state, updated_at) VALUES ({ph(3)}) ON CONFLICT (code) DO NOTHING',
                        (code, json.dumps(room), time.time()))
            if cur.rowcount:
                return snapshot(code, room, 0), token
    raise RoomError('Could not create a room. Please try again.', 503)


def join(code, name, token=''):
    with locked_room(code) as (code, room):
        if token:
            try:
                pid = authenticate(room, token)
                room['seats'][pid]['seen'] = time.time()
                return snapshot(code, room, pid), token
            except RoomError:
                pass
        if room['phase'] != 'lobby' or len(room['seats']) >= 4:
            raise RoomError('This room has started or all four seats are taken.', 409)
        token = secrets.token_urlsafe(32)
        room['seats'].append(new_seat(name, token))
        room['version'] += 1
        return snapshot(code, room, len(room['seats']) - 1), token


def load_state(room):
    return {'game': deserialize_game(room['game']), 'last_log': room['last_log'],
            'pending_log': room['pending_log']}


def store_state(room, state):
    room['game'] = serialize_game(state['game'])
    room['last_log'] = state['last_log'][-80:]
    room['pending_log'] = state['pending_log'][-80:]
    if state['game'].status == GameStatus.WON:
        room['phase'] = 'finished'


def snapshot(code, room, you, state=None):
    result = {'code': code, 'you': you, 'host': you == 0, 'version': room['version'],
              'mode': room['mode'], 'phase': room['phase'], 'paused': room['paused'],
              'notice': room['notice'], 'seats': [
                  {'player_id': i, 'name': s['name'], 'hero': s['hero'], 'ai': s['ai'],
                   'skip_next': s['skip_next'], 'online': time.time() - s['seen'] < ONLINE_SECONDS}
                  for i, s in enumerate(room['seats'])]}
    if room['game']:
        state = state or load_state(room)
        game = state['game']
        decision = interaction(game)
        public = build_state(lambda: state)
        for player in public['players']:
            player.pop('movement_deck_cards', None)
            if player['player_id'] != you:
                player['movement_hand'] = []
        for tile in public['board']:
            if not game.board[tile['index']].revealed:
                tile['tile_type'] = 'HIDDEN'
        owner = decision['player_id']
        result.update(state=public, decision=decision,
                      waiting_for_connection=owner is not None and not room['seats'][owner]['ai']
                      and time.time() - room['seats'][owner]['seen'] >= ONLINE_SECONDS)
        store_state(room, state)
    return result


def get(code, token):
    with locked_room(code) as (code, room):
        pid = authenticate(room, token)
        room['seats'][pid]['seen'] = time.time()
        state = load_state(room) if room['game'] else None
        if state:
            advance_computers(room, state)
        return snapshot(code, room, pid, state)


def _integer(body, key, minimum=0, maximum=100):
    value = body.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise RoomError(f'Invalid {key.replace("_", " ")}.')
    return value


def authorize(game, pid, action, body):
    decision = interaction(game)
    if decision['player_id'] != pid:
        raise RoomError('Wait for your turn or decision.', 403)
    phase = decision['phase']
    allowed = {
        'move': INVENTORY | {'begin_move', 'use_eight_lives', 'use_mages_gauntlet', 'use_consumable', 'use_pack_consumable', 'summon_monster', 'mutagen'},
        'combat': INVENTORY | {'fight', 'flee', 'swiftness_flee', 'use_ill_come_in_again', 'use_consumable', 'use_pack_consumable', 'crossroads_discard'},
        'bystander': {'bystander_consumable'}, 'me_too': {'resolve_me_too'},
        'trait_loss': {'resolve_trait_loss'},
        'item': {'place_trait_item'}, 'minion': {'resolve_minion'},
        'chest': {'resolve_offer', 'scavenger_swap'}, 'shop': {'resolve_offer', 'scavenger_swap'},
        'rake_it_in': {'resolve_rake_it_in'}, 'mystery': {'resolve_mystery'},
        'fairy_king_reward': {'resolve_fairy_king_reward'}, 'charlie_work': {'resolve_charlie_work'},
    }.get(phase, set())
    if action not in allowed:
        raise RoomError('That action is not available at this point in the turn.', 409)
    if action in ('place_trait_item', 'resolve_minion', 'bystander_consumable'):
        if body.get('player_id', pid) != pid:
            raise RoomError('You can only make choices for your own hero.', 403)
        body['player_id'] = pid
    if action in ('use_consumable', 'use_pack_consumable') and phase == 'combat' and not decision['consumables_allowed']:
        raise RoomError('The Watcher does not allow consumables in this fight.')
    if action == 'scavenger_swap' and not decision.get('scavenger'):
        raise RoomError('Scavenger is not available for this offer.')
    if action == 'begin_move':
        player = game.current_player
        _integer(body, 'card_index', 0, max(0, len(player.movement_hand) - 1))
        if body.get('direction', 'forward') not in ('forward', 'backward'):
            raise RoomError('Choose forward or backward.')
        activated = body.get('activated', {})
        if not isinstance(activated, dict):
            raise RoomError('Invalid abilities.')
        available = {a['id']: a for a in decision['abilities']}
        for key, value in activated.items():
            if key not in available or key == 'eight_lives':
                raise RoomError('That movement ability is not available.')
            ab = available[key]
            if ab['type'] in ('toggle', 'activate'):
                if type(value) is not bool:
                    raise RoomError('Invalid ability choice.')
            elif not isinstance(value, dict):
                raise RoomError('Invalid ability choice.')
            elif key == 'fancy_footwork':
                _integer(value, 'reduction', 1, 2)
            elif key == 'phase_shift':
                _integer(value, 'equip_index', 0, len(ab['equips']) - 1)
            elif key == 'meat_on_menu':
                target = next((t for t in ab['targets'] if t['player_id'] == value.get('target_player_id')), None)
                if target is None:
                    raise RoomError('Choose an opponent with minions.')
                _integer(value, 'minion_index', 0, len(target['minions']) - 1)


def invoke(state, action, body):
    """Run the existing handler against this transaction's private game instance."""
    g.werblers_room_state = state
    g.werblers_action_body = body
    try:
        if action == 'mutagen':
            game = state['game']
            target = _integer(body, 'target_player_id', 0, len(game.players) - 1)
            index = _integer(body, 'curse_index', 0, len(game.current_player.curses) - 1)
            log = game.use_contagious_mutagen(game.current_player.player_id, target, index)
            state['last_log'] = log
            return
        response = current_app.make_response(current_app.view_functions[HANDLERS[action]]())
        payload = response.get_json() or {}
        if response.status_code >= 400 or payload.get('error') or payload.get('ok') is False:
            raise RoomError(payload.get('error', 'That choice could not be applied.'), min(response.status_code if response.status_code >= 400 else 400, 499))
        if payload.get('log'):
            state['last_log'] = payload['log']
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise RoomError('Invalid choice. Refresh the room and try again.') from exc
    finally:
        g.pop('werblers_room_state', None)
        g.pop('werblers_action_body', None)


def skip_decision(room, state, pid):
    game = state['game']
    d = interaction(game)
    if d['player_id'] != pid:
        room['seats'][pid]['skip_next'] = True
        room['notice'] = f"{room['seats'][pid]['name']}'s next turn will be skipped."
        return
    phase = d['phase']
    if phase == 'trait_loss':
        state['last_log'] = game.resolve_trait_loss(d['choice']['id'], list(range(d['choice']['count'])))
    elif phase == 'me_too':
        game.resolve_me_too(d['choice']['id'])
    elif phase == 'bystander':
        game._pending_combat['nearby_queue'].remove(pid)
    elif phase in ('item', 'minion'):
        player = game.players[pid]
        player.pending_trait_items.clear()
        player.pending_trait_minions.clear()
        if game._rakeitin_pending_placement:
            game._rakeitin_pending_placement = False
            game._advance_turn()
    elif phase != 'finished':
        game._pending_offer = None
        game._pending_combat = None
        game._prefight_str_bonus = game._prefight_monster_str_bonus = 0
        game._rakeitin_pending_placement = False
        if phase == 'move':
            game.turn_number += 1
        game._advance_turn()
    room['notice'] = f"Host skipped {room['seats'][pid]['name']}'s {'turn' if phase in ('move', 'combat', 'chest', 'shop', 'mystery', 'charlie_work', 'rake_it_in') else 'decision'}. Completed actions are kept."
    state['last_log'] = state['last_log'] + [room['notice']]


def action(code, token, action, body):
    if not isinstance(body, dict):
        raise RoomError('Invalid action.')
    with locked_room(code) as (code, room):
        pid = authenticate(room, token)
        seat = room['seats'][pid]
        seat['seen'] = time.time()
        request_id = body.get('_request_id')
        if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', request_id):
            raise RoomError('Invalid request identifier.')
        state = load_state(room) if room['game'] else None
        if request_id in seat['requests']:
            return snapshot(code, room, pid, state)
        # Hero choices only touch the caller's lobby seat. Validate availability
        # under this lock so friends can select different heroes simultaneously.
        lobby_choice = action == 'hero' and room['phase'] == 'lobby'
        # Host controls target stable seats, so polling AI must not prevent a
        # pause or handover. Skips still require the exact decision version.
        host_control = pid == 0 and action in ('pause', 'resume', 'ai', 'human')
        if type(body.get('_version')) is not int or (body['_version'] != room['version'] and not (lobby_choice or host_control)):
            raise RoomError('The room changed. Syncing the latest state; please try again.', 409)
        if action == 'hero':
            hero = body.get('hero')
            if room['phase'] != 'lobby' or not isinstance(hero, str) or hero not in HeroId.__members__:
                raise RoomError('Choose a hero before the game starts.')
            if any(s['hero'] == hero for i, s in enumerate(room['seats']) if i != pid):
                raise RoomError('That hero has already been chosen.', 409)
            seat['hero'] = hero
        elif action == 'start':
            if pid != 0:
                raise RoomError('Only the host can start the game.', 403)
            if room['phase'] != 'lobby' or len(room['seats']) < 2 or any(s['hero'] is None for s in room['seats']):
                raise RoomError('Two to four players must choose heroes before starting.')
            game = Game(len(room['seats']), [HeroId[s['hero']] for s in room['seats']])
            for p, s in zip(game.players, room['seats']):
                p.name = s['name']
                game.draw_movement_cards(p)
            state = {'game': game, 'last_log': ['Online adventure started.'], 'pending_log': []}
            room['phase'] = 'playing'
        elif action in ('skip', 'ai', 'human', 'pause', 'resume'):
            if pid != 0:
                raise RoomError('Only the host can manage players or pause the room.', 403)
            if room['phase'] != 'playing':
                raise RoomError('The game is not in progress.')
            if action in ('pause', 'resume'):
                room['paused'] = action == 'pause'
            else:
                target = _integer(body, 'player_id', 0, len(room['seats']) - 1)
                if action == 'skip':
                    skip_decision(room, state, target)
                else:
                    room['seats'][target]['ai'] = action == 'ai'
                    room['seats'][target]['skip_next'] = False
                    room['notice'] = f"{room['seats'][target]['name']} is now controlled by {'AI' if action == 'ai' else 'their guest player'}."
        else:
            if state is None or room['phase'] != 'playing' or room['paused']:
                raise RoomError('The game is paused or not in progress.', 409)
            if seat['ai']:
                raise RoomError('The host must return your seat to human control first.', 403)
            authorize(state['game'], pid, action, body)
            invoke(state, action, body)
        seat['requests'] = (seat['requests'] + [request_id])[-64:]
        room['version'] += 1
        if state:
            # Do not run another seat until the caller has received their own outcome.
            store_state(room, state)
        return snapshot(code, room, pid, state)


def ai_choice(game, decision):
    """A conservative rules-based opponent, with no access to hidden deck order."""
    phase, pid = decision['phase'], decision['player_id']
    p = game.players[pid]
    if phase == 'trait_loss':
        indices = sorted(range(len(p.traits)), key=lambda i: p.traits[i].strength_bonus + p.traits[i].tokens)[:decision['choice']['count']]
        return 'resolve_trait_loss', {'choice_id': decision['choice']['id'], 'trait_indices': indices}
    if phase == 'me_too':
        index = min(range(len(p.curses)), key=lambda i: p.curses[i].strength_bonus)
        return 'resolve_me_too', {'choice_id': decision['choice']['id'], 'curse_index': index}
    if phase == 'bystander':
        return 'bystander_consumable', {'player_id': pid, 'skip': True}
    if phase == 'minion':
        index = min(range(len(p.minions)), key=lambda i: p.minions[i].strength_bonus) if p.minions else -1
        return 'resolve_minion', {'player_id': pid, 'replace_index': index,
                                 'discard': index >= 0 and p.minions[index].strength_bonus >= decision['minion']['strength_bonus']}
    if phase == 'charlie_work':
        return 'resolve_charlie_work', {'use_it': False}
    if phase == 'combat':
        pc = game._pending_combat
        if decision['can_flee'] and p.combat_strength(is_night=game.is_night) + game._prefight_str_bonus < pc['monster'].strength:
            return 'flee', {}
        if decision['consumables_allowed']:
            for i, c in enumerate(p.consumables):
                if (c.effect_id == '' and c.strength_bonus > 0) or (c.effect_id == 'monster_str_mod' and c.effect_value < 0):
                    return 'use_consumable', {'consumable_index': i}
        return 'fight', {}
    if phase == 'rake_it_in':
        return 'resolve_rake_it_in', {'use_it': False}
    if phase == 'mystery':
        event = decision['event']['event_id']
        return 'resolve_mystery', {'action': 'spin' if event == 'the_wheel' else 'skip'}
    if phase == 'fairy_king_reward':
        index = max(range(len(decision['items'])), key=lambda i: decision['items'][i]['strength_bonus'])
        return 'resolve_fairy_king_reward', {'choice_index': index}
    if phase in ('chest', 'shop', 'item'):
        items = p.pending_trait_items if phase == 'item' else game._pending_offer['items']
        index = max(range(len(items)), key=lambda i: items[i].strength_bonus)
        item = items[index]
        choices = {'placement': 'pack', 'pack_discard_index': 0}
        take = True
        if p.can_equip(item):
            choices['placement'] = 'equip'
        elif not item.is_consumable:
            slot = p._slot_list(item.slot)
            if slot:
                old_index = min(range(len(slot)), key=lambda i: slot[i].strength_bonus)
                displaced = slot[:2] if item.slot.value == 'weapon' and item.hands == 2 and len(slot) >= 2 else [slot[old_index]]
                try:
                    p.validate_equipment_replacement(item, displaced)
                    if item.strength_bonus > sum(i.strength_bonus for i in displaced):
                        choices.update(placement='equip', equip_action='discard', equip_action_2='discard', equip_item_index=old_index)
                except ValueError:
                    pass
        if choices['placement'] == 'pack' and p.pack_slots_free == 0:
            take = False
        if phase == 'item':
            return 'place_trait_item', {'player_id': pid, 'placement_choices': choices if take else {'discard': True}}
        return 'resolve_offer', {'take': take, 'chosen_index': index, **choices}
    return 'begin_move', {'card_index': max(range(len(p.movement_hand)), key=p.movement_hand.__getitem__),
                          'direction': 'forward', 'activated': {}}


def advance_computers(room, state):
    if room['paused'] or room['phase'] != 'playing':
        return
    # Bound each request. More AI decisions continue on the next room refresh.
    for _ in range(8):
        d = interaction(state['game'])
        pid = d['player_id']
        if pid is None:
            break
        seat = room['seats'][pid]
        if seat['skip_next'] and d['phase'] == 'move':
            seat['skip_next'] = False
            skip_decision(room, state, pid)
        elif seat['ai']:
            action_name, body = ai_choice(state['game'], d)
            before = serialize_game(state['game'])
            try:
                authorize(state['game'], pid, action_name, body)
                invoke(state, action_name, body)
            except RoomError:
                state['game'] = deserialize_game(before)
                room['paused'] = True
                room['notice'] = 'AI could not finish a decision. The host can skip it or return the seat to human control, then resume.'
                room['version'] += 1
                break
        else:
            break
        room['version'] += 1
    store_state(room, state)
