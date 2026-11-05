"""Authoritative pending decision, shared by local recovery and private rooms."""
from copy import deepcopy
from werblers_engine.types import GameStatus
from werblers_web.serializers import ser_item, enrich_combat_info


def interaction(game, *, online=True):
    """One authoritative decision owner, including out-of-turn reactions/rewards."""
    if game.status != GameStatus.IN_PROGRESS:
        return {'phase': 'finished', 'player_id': None}
    if game._pending_trait_loss:
        choice = game._pending_trait_loss
        return {"phase": "trait_loss", "player_id": choice["player_id"],
                "choice": {k: choice[k] for k in ("id", "player_id", "count")}}
    choice = game.pending_me_too()
    if choice:
        return {'phase': 'me_too', 'player_id': choice['player_id'], 'choice': choice}
    for p in game.players:
        if p.pending_trait_items:
            return {'phase': 'item', 'player_id': p.player_id, 'items': [ser_item(p.pending_trait_items[0])]}
        if p.pending_trait_minions:
            m = p.pending_trait_minions[0]
            return {'phase': 'minion', 'player_id': p.player_id,
                    'minion': {'name': m.name, 'strength_bonus': m.strength_bonus}}
    pid = game.current_player.player_id
    pc = game._pending_combat
    if pc:
        if pc.get('type') == 'awaiting_charlie_work':
            return {'phase': 'charlie_work', 'player_id': pid, 'level': pc['level']}
        # Initialize once; do not re-add a bystander who already chose to pass.
        if 'nearby_queue' not in pc:
            pc['nearby_queue'] = [p.player_id for p in game.players if p.player_id != pid
                                  and abs(p.position - game.current_player.position) <= 5
                                  and any(c.effect_id == 'monster_str_mod' for c in p.consumables)]
        phase, owner = ('bystander', pc['nearby_queue'][0]) if online and pc['nearby_queue'] else ('combat', pid)
        info = deepcopy(game._last_combat_info or {})
        if online:
            info['nearby_queue'] = []  # the room owns the reaction queue
        else:
            info.pop('nearby_queue', None)  # reconstruct only unanswered reactions
        return {'phase': phase, 'player_id': owner,
                'combat': enrich_combat_info(info, game, lambda: {'pending_log': []}),
                'can_flee': bool(game.current_player.hero and (
                    game.current_player.hero.can_flee_miniboss if pc.get('type') == 'miniboss'
                    else game.current_player.hero.can_flee_monsters)) and pc.get('type') != 'werbler',
                'consumables_allowed': pc['monster'].effect_id != 'the_watcher'}
    po = game._pending_offer
    if po:
        phase = po['type']
        result = {'phase': phase, 'player_id': pid}
        if phase in ('chest', 'shop'):
            result['items'] = [ser_item(i) for i in po['items']]
            result['scavenger'] = game.can_scavenge()
        elif phase == 'rake_it_in':
            result.update(sub_type=po['sub_type'], items=[ser_item(i) for i in po.get('shop_remaining', [])])
        elif phase == 'mystery':
            from dataclasses import asdict
            result['event'] = asdict(po['event'])
        elif phase == 'fairy_king_reward':
            result['items'] = [ser_item(i) for i in po['reward_items']]
        return result
    return {'phase': 'move', 'player_id': pid, 'abilities': game.get_available_abilities()}
