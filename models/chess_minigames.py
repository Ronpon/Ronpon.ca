"""Server-side Battle Chess minigames. Times are seconds, positions are pixels.

The room's database transaction owns this state. No worker-local timers or
client-supplied positions, scores, decks, or winners are trusted.
"""
import math
import secrets

GAMES = ('highest-card', 'memory-match', 'mashing-battle', 'timing-battle', 'dodging-battle')
LIVE_GAMES = ('mashing-battle', 'timing-battle', 'dodging-battle')
STEP = 0.02
DISCONNECT_AFTER = 2.0


class BattleError(ValueError):
    pass


def other(color):
    return 'b' if color == 'w' else 'w'


def advantaged(attacker, advantage):
    return attacker if advantage == 'attacker' else other(attacker) if advantage == 'defender' else None


def create(game, attacker, move, advantage, now):
    battle = dict(id=secrets.token_hex(8), gameId=game, attacker=attacker, move=move,
                  advantage=advantage, ready=[], startReady=[], outcome=None,
                  phase='playing' if game in ('highest-card', 'memory-match') else 'ready')
    favored = advantaged(attacker, advantage)
    if game in ('highest-card', 'memory-match'):
        deck = list(range(52))
        secrets.SystemRandom().shuffle(deck)
        battle.update(deck=deck, picks={})
    if game == 'memory-match':
        battle.update(turn=attacker, turnNumber=1, flipped=[], hideAt=None,
                      targets={c: 3 if c == favored else 4 for c in ('w', 'b')})
    if game in LIVE_GAMES:
        battle.update(lastSeen={'w': now, 'b': now}, seq={'w': 0, 'b': 0},
                      startAt=None, pausedAt=None, elapsed=0, lastTick=now,
                      controls={c: dict(keys=0, at=now, budget=8, budgetAt=now) for c in ('w', 'b')})
    if game in ('mashing-battle', 'timing-battle'):
        battle['position'] = 5 if favored == 'w' else 3 if favored == 'b' else 4
    if game == 'mashing-battle':
        battle.update(presses={'w': 0, 'b': 0}, endsAt=None)
    if game == 'timing-battle':
        battle.update(round=0, stage='waiting', cueAt=None, cue=None, reactions={}, cueSeen={}, nextRoundAt=None, message='')
    if game == 'dodging-battle':
        battle.update(actors={c: dict(x=120 if c == 'w' else 280, y=200, lives=2 if c == favored else 1)
                              for c in ('w', 'b')}, projectiles=[], spawnTimer=0, extraLife=None)
    return battle


def finish(battle, winner):
    battle['outcome'] = 'tie' if winner is None else 'attacker' if winner == battle['attacker'] else 'defender'
    battle['phase'] = 'result'


def ready(battle, color, now):
    if battle['gameId'] not in LIVE_GAMES or battle['phase'] not in ('ready', 'paused'):
        raise BattleError('This battle is already running.')
    if color not in battle['startReady']:
        battle['startReady'].append(color)
    battle['lastSeen'][color] = now
    if len(battle['startReady']) < 2:
        return
    start = now + 3
    if battle['pausedAt'] is not None:
        shift = start - battle['pausedAt']
        for key in ('endsAt', 'cueAt', 'nextRoundAt'):
            if battle.get(key) is not None:
                battle[key] += shift
        for c in battle.get('cueSeen', {}):
            battle['cueSeen'][c] += shift
        battle['pausedAt'] = None
        if battle['gameId'] == 'timing-battle':
            # Replaying a visible cue after a pause would reward anticipation.
            # Keep the score, but give both players a fresh reaction round.
            _timing_round(battle, start)
        if battle['gameId'] == 'dodging-battle':
            battle['extraLife'] = None
    else:
        if battle['gameId'] == 'mashing-battle':
            battle['endsAt'] = start + 20
        elif battle['gameId'] == 'timing-battle':
            _timing_round(battle, start)
    battle.update(phase='countdown', startAt=start, lastTick=start, startReady=[])
    for control in battle['controls'].values():
        control['keys'] = 0


def advance(battle, now):
    """Advance on requests, bounded by presence and fixed physics steps."""
    game = battle['gameId']
    if battle['outcome'] is not None:
        return
    if game == 'memory-match':
        if battle['hideAt'] is not None and now >= battle['hideAt']:
            battle.update(flipped=[], hideAt=None, turn=other(battle['turn']), turnNumber=battle['turnNumber'] + 1)
        return
    if game not in LIVE_GAMES or battle['phase'] in ('ready', 'paused'):
        return
    cutoff = min(now, min(battle['lastSeen'].values()) + DISCONNECT_AFTER)
    if battle['phase'] == 'countdown' and cutoff >= battle['startAt']:
        battle['phase'] = 'playing'
    if battle['phase'] == 'playing':
        if game == 'mashing-battle' and cutoff >= battle['endsAt']:
            finish(battle, 'w' if battle['position'] > 4 else 'b' if battle['position'] < 4 else None)
        elif game == 'timing-battle':
            if battle['stage'] == 'result' and cutoff >= battle['nextRoundAt']:
                _timing_round(battle, cutoff)
            if battle['stage'] == 'waiting' and cutoff >= battle['cueAt']:
                battle.update(stage='signal', cue=secrets.token_hex(12))
            if battle['stage'] == 'signal' and cutoff >= battle['cueAt'] + 2:
                _judge_timing(battle, cutoff)
        elif game == 'dodging-battle':
            # At most 2s of catch-up before a disconnected match pauses.
            while battle['lastTick'] + STEP <= cutoff and battle['phase'] == 'playing':
                battle['lastTick'] += STEP
                _dodge_step(battle)
    if cutoff < now and battle['outcome'] is None:
        battle.update(phase='paused', pausedAt=max(cutoff, battle['startAt']), startReady=[])
        for control in battle['controls'].values():
            control['keys'] = 0


def flip(battle, color, index, turn_number, now):
    if battle['gameId'] != 'memory-match' or battle['outcome'] is not None:
        raise BattleError('Memory Match is not running.')
    if color != battle['turn'] or turn_number != battle['turnNumber'] or battle['hideAt'] is not None:
        raise BattleError('Wait for your turn to flip cards.')
    if type(index) is not int or not 0 <= index < 52 or index in battle['flipped']:
        raise BattleError('Choose a face-down card.')
    battle['flipped'].append(index)
    if len(battle['flipped']) == battle['targets'][color]:
        if len({battle['deck'][i] % 13 for i in battle['flipped']}) == 1:
            finish(battle, color)
        else:
            battle['hideAt'] = now + 2


def input_frame(battle, color, data, now):
    """Sequenced, retryable control frames; one seat cannot control the other."""
    if battle['gameId'] not in LIVE_GAMES:
        raise BattleError('This game does not use live controls.')
    seq, keys, taps = data.get('seq'), data.get('keys', 0), data.get('taps', 0)
    if type(seq) is not int or not 1 <= seq <= 2**31 or type(keys) is not int or not 0 <= keys <= 15 or type(taps) is not int or not 0 <= taps <= 8:
        raise BattleError('Invalid control frame.')
    if seq <= battle['seq'][color]:
        return
    battle['seq'][color] = seq
    battle['lastSeen'][color] = now
    control = battle['controls'][color]
    control['keys'] = keys
    control['at'] = now
    if battle['outcome'] is not None or battle['phase'] != 'playing':
        return
    if battle['gameId'] == 'mashing-battle':
        # Allow ordinary human bursts, but not arbitrary client-supplied scores.
        control['budget'] = min(8, control['budget'] + max(0, now - control['budgetAt']) * 25)
        control['budgetAt'] = now
        accepted = min(taps, int(control['budget']))
        control['budget'] -= accepted
        before = battle['presses'][color] // 5
        battle['presses'][color] += accepted
        notches = battle['presses'][color] // 5 - before
        battle['position'] = max(0, min(8, battle['position'] + notches * (1 if color == 'w' else -1)))
    elif battle['gameId'] == 'timing-battle':
        if data.get('press') is True and data.get('round') == battle['round'] and color not in battle['reactions'] and battle['stage'] in ('waiting', 'signal'):
            if battle['stage'] == 'waiting' or data.get('cue') != battle['cue']:
                battle['reactions'][color] = -1
            elif color in battle['cueSeen']:
                # Measure on the server from the signal sent to this player.
                # This removes polling-order bias without trusting client clocks.
                battle['reactions'][color] = round(max(0, now - battle['cueSeen'][color]) * 1000)
            if len(battle['reactions']) == 2:
                _judge_timing(battle, now)


def signal_seen(battle, color, now):
    if battle.get('gameId') == 'timing-battle' and battle['phase'] == 'playing' and battle['stage'] == 'signal':
        battle['cueSeen'].setdefault(color, now)


def _timing_round(battle, now):
    battle.update(round=battle['round'] + 1, stage='waiting', cueAt=now + 2 + secrets.randbelow(4001) / 1000,
                  reactions={}, cueSeen={}, cue=None, nextRoundAt=None, message='Wait for NOW!')


def _judge_timing(battle, now):
    w, b = battle['reactions'].get('w'), battle['reactions'].get('b')
    winner = None
    if w == -1 and b != -1:
        winner = 'b'
    elif b == -1 and w != -1:
        winner = 'w'
    elif w is not None and w >= 0 and (b is None or b > w):
        winner = 'w'
    elif b is not None and b >= 0 and (w is None or w > b):
        winner = 'b'
    battle['position'] += 1 if winner == 'w' else -1 if winner == 'b' else 0
    battle.update(stage='result', nextRoundAt=now + 1.8,
                  message=('White wins this round.' if winner == 'w' else 'Black wins this round.' if winner == 'b' else 'No point this round.'))
    if battle['position'] in (0, 8):
        finish(battle, 'w' if battle['position'] == 8 else 'b')


def _dodge_step(battle):
    dt = STEP
    battle['elapsed'] += dt
    for color, actor in battle['actors'].items():
        control = battle['controls'][color]
        # Lost key-up messages never leave a player moving indefinitely.
        keys = control['keys'] if battle['lastTick'] - control['at'] < .35 else 0
        dx, dy = bool(keys & 8) - bool(keys & 4), bool(keys & 2) - bool(keys & 1)
        length = math.hypot(dx, dy) or 1
        actor['x'] = max(16, min(384, actor['x'] + dx / length * 180 * dt))
        actor['y'] = max(16, min(384, actor['y'] + dy / length * 180 * dt))
    if battle['elapsed'] >= 1.5:
        battle['spawnTimer'] += dt
        if battle['spawnTimer'] >= max(.15, 1.2 - (battle['elapsed'] - 1.5) * .04):
            battle['spawnTimer'] = 0
            _spawn(battle)
    speed = 120 + battle['elapsed'] * 12
    for p in battle['projectiles']:
        p['x'] += p['vx'] * speed * dt
        p['y'] += p['vy'] * speed * dt
    battle['projectiles'] = [p for p in battle['projectiles'] if -20 < p['x'] < 420 and -20 < p['y'] < 420]
    hit = [c for c, a in battle['actors'].items() if any(math.hypot(a['x'] - p['x'], a['y'] - p['y']) < 21 for p in battle['projectiles'])]
    for c in hit:
        battle['actors'][c]['lives'] -= 1
    dead = [c for c, a in battle['actors'].items() if a['lives'] <= 0]
    if dead:
        finish(battle, None if len(dead) == 2 else other(dead[0]))
    elif hit:
        battle.update(projectiles=[], phase='countdown', startAt=battle['lastTick'] + 5, extraLife=hit[0])
        battle['lastTick'] = battle['startAt']


def _spawn(battle):
    edge, pos = secrets.randbelow(4), secrets.randbelow(40000) / 100
    x, y = ((pos, -10), (410, pos), (pos, 410), (-10, pos))[edge]
    target_x, target_y = 80 + secrets.randbelow(24000) / 100, 80 + secrets.randbelow(24000) / 100
    angle = math.atan2(target_y - y, target_x - x)
    battle['projectiles'].append(dict(x=x, y=y, vx=math.cos(angle), vy=math.sin(angle)))


def public(battle, color):
    """Explicit allowlists keep card decks and future timing cues private."""
    keys = ['id', 'gameId', 'attacker', 'move', 'ready', 'outcome', 'phase', 'startReady', 'choiceBy']
    game = battle.get('gameId', 'highest-card')
    if game == 'highest-card':
        keys += ['picks']
    elif game == 'memory-match':
        keys += ['turn', 'turnNumber', 'flipped', 'targets', 'hideAt']
    elif game in LIVE_GAMES:
        keys += ['startAt', 'position', 'presses', 'endsAt', 'elapsed', 'actors', 'projectiles', 'extraLife', 'round', 'stage', 'reactions', 'message']
    state = {key: battle[key] for key in keys if key in battle}
    state.setdefault('gameId', game)
    if game == 'highest-card':
        state['cards'] = {side: battle['deck'][index] for side, index in battle['picks'].items()} if battle['outcome'] is not None else None
    elif game == 'memory-match':
        state['cards'] = {str(i): battle['deck'][i] for i in battle['flipped']}
    elif game in LIVE_GAMES:
        state['ack'] = battle['seq'][color]
        if game == 'timing-battle':
            state['cue'] = battle['cue'] if battle['stage'] == 'signal' and battle['phase'] == 'playing' else None
    return state
