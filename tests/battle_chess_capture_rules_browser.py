"""Real-browser regression checks for capture battle outcomes.

Run: .venv/Scripts/python.exe tests/battle_chess_capture_rules_browser.py
Use --url to check a deployed game or --static-root to serve staged game assets.
Local runs use temporary databases. All chess/card fixtures stay in the browser;
the test never creates an online room or writes to a deployed application.
"""
import argparse
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server, WSGIRequestHandler
from test_site_theme import isolated_app


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def move(ui, source, target):
    canvas = ui.locator('#game-canvas')
    rect = canvas.bounding_box()
    for square in (source, target):
        canvas.click(position={
            'x': (ord(square[0]) - 97 + .5) * rect['width'] / 8,
            'y': (8 - int(square[1]) + .5) * rect['height'] / 8,
        })


def solo_setup(page, url, human, remove_attacker):
    page.goto(url)
    ui = page.frame_locator('iframe')
    ui.locator('#btn-1p').click()
    frame = next(frame for frame in page.frames if '/static/games/battle-chess/' in frame.url)
    frame.evaluate("""() => {
        const app = window.app;
        window.captureChecks = {setup: null, resolutions: [], gameOvers: [], aiRequests: [], moves: []};
        // Only the engine's answer is controlled: its normal scheduled turn still
        // calls attemptMove and starts the same capture battle as a real search.
        app.gameManager.chessAI.chooseMove = async (fen) => {
            captureChecks.aiRequests.push(fen);
            return captureChecks.moves.shift() || null;
        };
        app.eventBus.on('setupComplete', config => {
            captureChecks.setup = JSON.parse(JSON.stringify(config));
        });
        app.eventBus.on('minigameEnd', () => {
            captureChecks.resolutions.push(JSON.parse(JSON.stringify({
                state: app.gameManager.state,
                game: app.gameManager.getGameState(),
                pending: app.gameManager.pendingMove,
                legalMoves: app.gameManager.chess.moves({verbose: true})
            })));
        });
        app.eventBus.on('gameOver', state => captureChecks.gameOvers.push(state));
    }""")
    ui.get_by_label('Chess difficulty', exact=True).select_option('easy')
    ui.get_by_label('Battle AI difficulty', exact=True).select_option('hard')
    ui.locator('#human-color').select_option(human)
    ui.locator('#btn-next-solo').click()
    ui.locator('.setup-name-input').fill('Capture tester')
    ui.locator('#btn-next-profiles').click()
    ui.locator('.setup-mg-check[data-id="highest-card"]').check()
    ui.locator('#btn-next-minigames').click()
    ui.locator('#adv-none').click()
    ui.locator('#rule-yes' if remove_attacker else '#rule-no').click()
    config = frame.evaluate('() => captureChecks.setup')
    assert config['playerCount'] == 1
    assert config['attackerLosesPiece'] is remove_attacker
    assert config['selectedMinigames'] == ['highest-card']
    assert config['players'][0]['color'] == 'w' and config['players'][1]['color'] == 'b'
    assert config['players'][0].get('isAI', False) is (human == 'b')
    assert config['players'][1].get('isAI', False) is (human == 'w')
    ui.locator('#view-classic').click()
    return ui, frame


def highest_card_result(ui, frame, winner, consequence):
    expect(ui.locator('.mg-screen')).to_be_visible()
    expect(ui.locator('.check-warning-panel')).to_have_count(0)
    ui.get_by_role('button', name='Got It', exact=True).click()
    # A computer attacker chooses first automatically; a computer defender chooses
    # after the human. Both use the actual Highest Card bot and click handlers.
    frame.wait_for_function("""() => {
        const game = window.app.minigameScreen._gameInstance;
        return game && !game.isAI(game.currentPicker);
    }""")
    index = frame.evaluate("""() => {
        const game = window.app.minigameScreen._gameInstance;
        return game.deck.findIndex((card, index) => index !== game.p1Choice && index !== game.p2Choice);
    }""")
    ui.locator(f'.hc-card[data-index="{index}"]').click()
    frame.wait_for_function("() => window.app.minigameScreen._gameInstance?.phase === 'reveal-ready'")
    # Make only the revealed outcome deterministic after both ordinary picks.
    frame.evaluate("""winner => {
        const game = window.app.minigameScreen._gameInstance;
        const choices = [game.p1Choice, game.p2Choice];
        choices.forEach((index, player) => {
            const wins = player === (winner === 'w' ? 0 : 1);
            game.deck[index].rank = wins ? 14 : 2;
            game.deck[index].value = wins ? 'A' : '2';
        });
    }""", winner)
    ui.get_by_role('button', name='Reveal', exact=True).click()
    expect(ui.locator('.mg-result-consequence')).to_have_text(consequence, timeout=10000)
    ui.locator('.mg-continue-btn').click(timeout=10000)
    expect(ui.locator('.mg-screen')).to_have_count(0)
    frame.wait_for_function('() => captureChecks.resolutions.length === 1')


def piece_at(snapshot, square):
    return snapshot['game']['board'][8 - int(square[1])][ord(square[0]) - 97]


def capture_case(ui, frame, *, label, fen, source, target, human,
                 attacker_wins=False, keep_turn=False, followup):
    attacker = fen.split()[1]
    defender = 'b' if attacker == 'w' else 'w'
    ai_attacker = attacker != human
    next_turn = attacker if keep_turn and not attacker_wins else defender
    followup_is_ai = next_turn != human
    ai_moves = []
    if ai_attacker:
        ai_moves.append({'from': source, 'to': target})
    if followup_is_ai:
        ai_moves.append({'from': followup[0], 'to': followup[1]})
    initial = frame.evaluate("""({fen, source, target, aiMoves}) => {
        const app = window.app;
        const manager = app.gameManager;
        manager.reset();
        manager.startGame();
        captureChecks.resolutions = [];
        captureChecks.gameOvers = [];
        captureChecks.aiRequests = [];
        captureChecks.moves = aiMoves;
        if (!manager.chess.load(fen)) throw new Error('Invalid capture fixture');
        const capture = manager.chess.moves({square: source, verbose: true})
            .find(move => move.to === target && move.captured);
        if (!capture) throw new Error('Fixture capture must be a legal chess move');
        const before = {attacker: manager.chess.get(source), defender: manager.chess.get(target),
            removeAttacker: manager.config.attackerLosesPiece};
        app.eventBus.emit('boardUpdated', manager.getGameState());
        return before;
    }""", {'fen': fen, 'source': source, 'target': target, 'aiMoves': ai_moves})
    if ai_attacker:
        expect(ui.locator('.mg-screen')).to_be_visible(timeout=10000)
        requests = frame.evaluate('() => captureChecks.aiRequests')
        assert requests and requests[0] == fen, label
    else:
        move(ui, source, target)
    assert frame.evaluate("""({source, target}) => {
        const pending = window.app.gameManager.pendingMove;
        return pending?.from === source && pending?.to === target;
    }""", {'source': source, 'target': target}), label
    if attacker_wins:
        consequence = 'The capture succeeds. The defending piece is taken.'
    elif initial['attacker']['type'] == 'k':
        consequence = 'The capture fails. The king and defending piece stay on the board.'
    elif initial['removeAttacker']:
        consequence = 'The attacking piece is removed. The defending piece stays.'
    else:
        consequence = 'The capture fails. Both pieces stay on the board.'
    highest_card_result(ui, frame, attacker if attacker_wins else defender, consequence)
    resolved = frame.evaluate('() => captureChecks.resolutions[0]')
    assert resolved['state'] == 'PLAYING', (label, resolved)
    assert resolved['pending'] is None, label
    assert not resolved['game']['isGameOver'], label
    assert resolved['game']['turn'] == next_turn, label
    if attacker_wins:
        assert piece_at(resolved, source) is None, label
        assert piece_at(resolved, target) == initial['attacker'], label
    else:
        expected_attacker = None if initial['removeAttacker'] else initial['attacker']
        assert piece_at(resolved, source) == expected_attacker, label
        assert piece_at(resolved, target) == initial['defender'], label
    if keep_turn:
        assert resolved['game']['isCheck'], label
        assert any(move['piece'] == 'k' and not move.get('captured') for move in resolved['legalMoves']), label
    expect(ui.get_by_role('heading', name='Game Over', exact=True)).to_have_count(0)
    if followup_is_ai:
        frame.wait_for_function("""({target, color}) => {
            const manager = window.app.gameManager;
            const piece = manager.chess.get(target);
            return manager.state === 'PLAYING' && piece?.type === 'k'
                && piece.color === color && manager.chess.turn() !== color;
        }""", arg={'target': followup[1], 'color': next_turn})
    else:
        move(ui, *followup)
        assert frame.evaluate("""({target, color}) => {
            const piece = window.app.gameManager.chess.get(target);
            return piece?.type === 'k' && piece.color === color;
        }""", {'target': followup[1], 'color': next_turn}), label
    assert frame.evaluate("() => window.app.gameManager.state === 'PLAYING' && captureChecks.gameOvers.length === 0"), label
    print('PASS:', label, flush=True)


def exercise(url):
    with sync_playwright() as playwright:
        edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
        page = browser.new_page(viewport={'width': 1100, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            for human in ('w', 'b'):
                ui, frame = solo_setup(page, url, human, True)
                ai = 'b' if human == 'w' else 'w'
                for ai_attacks in (True, False):
                    attacker = ai if ai_attacks else human
                    capture_case(ui, frame, label=f'{human}: failed {"AI" if ai_attacks else "human"} attack removes only attacker',
                                 fen=f'4k3/8/8/3p4/4P3/8/8/4K3 {attacker} - - 0 1',
                                 source='e4' if attacker == 'w' else 'd5', target='d5' if attacker == 'w' else 'e4',
                                 human=human, followup=('e1', 'f1') if (human if ai_attacks else ai) == 'w' else ('e8', 'f8'))
                capture_case(ui, frame, label=f'{human}: successful capture replaces defender',
                             fen=f'4k3/8/8/3p4/4P3/8/8/4K3 {human} - - 0 1',
                             source='e4' if human == 'w' else 'd5', target='d5' if human == 'w' else 'e4',
                             human=human, attacker_wins=True, followup=('e8', 'f8') if ai == 'b' else ('e1', 'f1'))
                if ai == 'w':
                    check_fen, check_capture, escape = '7k/7p/8/8/4r3/3B4/P7/4K3 w - - 0 1', ('d3', 'e4'), ('e1', 'f1')
                else:
                    check_fen, check_capture, escape = '4k3/7p/3b4/4R3/8/8/P7/K7 b - - 0 1', ('d6', 'e5'), ('e8', 'f8')
                capture_case(ui, frame, label=f'{human}: AI loses capture in check, removes attacker and makes legal escape',
                             fen=check_fen, source=check_capture[0], target=check_capture[1], human=human,
                             keep_turn=True, followup=escape)
                if human == 'w':
                    for label, fen, source, target in (
                        ('human capture in check', '7k/7p/8/8/4r3/3B4/P7/4K3 w - - 0 1', 'd3', 'e4'),
                        ('human pinned attacker', 'k3r3/7p/8/8/8/8/4R3/4K3 w - - 0 1', 'e2', 'e8'),
                    ):
                        capture_case(ui, frame, label=f'w: failed {label} permits legal escape without battle forfeit',
                                     fen=fen, source=source, target=target, human=human,
                                     keep_turn=True, followup=('e1', 'f1'))
                ui, frame = solo_setup(page, url, human, False)
                capture_case(ui, frame, label=f'{human}: rule No preserves both pieces and passes turn',
                             fen=f'4k3/8/8/3p4/4P3/8/8/4K3 {ai} - - 0 1',
                             source='e4' if ai == 'w' else 'd5', target='d5' if ai == 'w' else 'e4',
                             human=human, followup=('e1', 'f1') if human == 'w' else ('e8', 'f8'))
            assert not errors, errors
            print('PASS: capture rules, both solo colors, scheduled AI captures, actual card outcomes, check responses, and continued play; no browser errors.')
        finally:
            browser.close()


def run(url=None, static_root=None):
    if url:
        exercise(url)
        return
    with tempfile.TemporaryDirectory(prefix='battle-chess-capture-rules-') as directory:
        app, _ = isolated_app(directory)
        if static_root:
            from flask import request, send_from_directory
            game_root = Path(static_root) / 'static/games/battle-chess'

            @app.before_request
            def staged_game():
                prefix = '/static/games/battle-chess/'
                if request.path.startswith(prefix):
                    return send_from_directory(game_root, request.path[len(prefix):])

        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            exercise(f'http://127.0.0.1:{server.server_port}/games/battle-chess')
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url')
    parser.add_argument('--static-root')
    args = parser.parse_args()
    run(args.url, args.static_root)
