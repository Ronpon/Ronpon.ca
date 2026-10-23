"""Solo setup, chess AI, and all five local battle bots in a real browser.

Run: .venv/Scripts/python.exe tests/battle_chess_ai_browser.py
Requires Playwright and Edge/Chromium; uses temporary databases only.
"""
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


def move(frame, source, target):
    fantasy = frame.locator('#fantasy-canvas')
    if fantasy.is_visible():
        for square in (source, target):
            point = fantasy.evaluate('(canvas, square) => window.app.board.fantasy.squareToScreen(square)', square)
            fantasy.click(position=point)
        return
    canvas = frame.locator('#game-canvas')
    rect = canvas.bounding_box()
    for square in (source, target):
        canvas.click(position={'x': (ord(square[0]) - 97 + .5) * rect['width'] / 8,
                               'y': (8 - int(square[1]) + .5) * rect['height'] / 8})


def wait(frame, expression, timeout=10000):
    frame.wait_for_function(expression, timeout=timeout)


def fixture(frame, game, mode='random', human='w', fen=None):
    frame.evaluate("""({game, mode, human, fen}) => {
        const app = window.app;
        app.gameManager.reset();
        app.setupWizard.hide();
        app.gameManager.startGame({
            playerCount: 1, chessDifficulty: 'easy', aiDifficulty: 'hard',
            players: ['w', 'b'].map(color => ({color, name: color === human ? 'Human' : 'Computer',
                icon: color === human ? '⚔️' : '🤖', isAI: color !== human})),
            selectedMinigames: game ? [game] : [], minigameMode: mode,
            minigameAdvantage: 'none', attackerLosesPiece: false
        });
        if (fen) {
            app.gameManager.chess.load(fen);
            app.eventBus.emit('boardUpdated', app.gameManager.getGameState());
        }
    }""", dict(game=game, mode=mode, human=human, fen=fen))


def capture(frame, ui, game, mode='random'):
    fixture(frame, game, mode, fen='4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1')
    move(ui, 'e4', 'd5')
    expect(ui.locator('.mg-screen')).to_be_visible()
    expect(ui.locator('.mg-sidebar-right .mg-controls-hint')).to_contain_text('Computer controlled')
    ui.get_by_role('button', name='Got It', exact=True).click()
    wait(frame, '() => !!window.app.minigameScreen._gameInstance')


def finish(ui):
    expect(ui.locator('.mg-continue-btn')).to_be_visible(timeout=10000)
    ui.locator('.mg-continue-btn').click()
    expect(ui.locator('.mg-screen')).to_have_count(0)


def run():
    with tempfile.TemporaryDirectory(prefix='battle-chess-ai-') as directory:
        app, _ = isolated_app(directory)
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
                page = browser.new_page(viewport={'width': 1100, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/games/battle-chess')
                ui = page.frame_locator('iframe')
                ui.locator('#btn-1p').click()
                frame = next(frame for frame in page.frames if '/static/games/battle-chess/' in frame.url)
                ui.get_by_label('Chess difficulty', exact=True).select_option('easy')
                ui.get_by_label('Battle AI difficulty', exact=True).select_option('hard')
                ui.locator('#human-color').select_option('b')
                # Both independent difficulty choices survive Back navigation.
                ui.get_by_role('button', name='Back', exact=True).click()
                ui.locator('#btn-1p').click()
                expect(ui.locator('#chess-difficulty')).to_have_value('easy')
                expect(ui.locator('#ai-difficulty')).to_have_value('hard')
                expect(ui.locator('#human-color')).to_have_value('b')
                ui.get_by_role('button', name='Continue', exact=True).click()
                expect(ui.locator('.setup-name-input')).to_have_count(1)
                ui.locator('.setup-name-input').fill('Solo tester')
                ui.locator('#btn-next-profiles').click()
                ui.locator('#btn-next-minigames').click()
                wait(frame, '() => window.app.gameManager.chess.history().length === 1')
                assert frame.evaluate("() => {const c = window.app.gameManager.config; return c.playerCount === 1 && c.chessDifficulty === 'easy' && c.aiDifficulty === 'hard' && c.players[0].isAI && !c.players[1].isAI;}")
                expect(ui.locator('#turn-indicator')).to_contain_text('Solo tester (Black)')
                ui.locator('#view-classic').click()
                # Playing Black permits a human reply, followed by the computer.
                frame.evaluate("() => {const m = window.app.gameManager; const move = m.chess.moves({verbose:true})[0]; m.attemptMove(move.from, move.to);}")
                wait(frame, '() => window.app.gameManager.chess.history().length === 3')

                # Computer captures use the real battle flow and choose for themselves.
                fixture(frame, 'highest-card', mode='attackerChoice', fen='7k/7R/4BK2/8/8/8/8/8 b - - 0 1')
                expect(ui.locator('.mg-screen')).to_be_visible(timeout=10000)
                assert frame.evaluate("() => window.app.gameManager.pendingMove.from === 'h8' && window.app.gameManager.pendingMove.to === 'h7'")
                expect(ui.locator('.mg-chooser-panel')).to_have_count(0)
                ui.get_by_role('button', name='Got It', exact=True).click()
                wait(frame, '() => window.app.minigameScreen._gameInstance.p2Choice !== null')
                frame.evaluate('() => window.app.gameManager.reset()')
                expect(ui.locator('.mg-screen')).to_have_count(0)

                # Highest Card automatically picks the computer card after the human.
                capture(frame, ui, 'highest-card', mode='defenderChoice')
                # Ensure a deterministic non-tie while retaining the real random bot pick.
                frame.evaluate("() => { const game = window.app.minigameScreen._gameInstance; game.deck.forEach((card, index) => card.rank = index); }")
                ui.locator('.hc-card').first.click()
                wait(frame, '() => window.app.minigameScreen._gameInstance.p2Choice !== null')
                ui.get_by_role('button', name='Reveal', exact=True).click()
                finish(ui)

                # Memory AI takes a complete turn without reading hidden cards.
                capture(frame, ui, 'memory-match')
                indices = frame.evaluate("() => { const deck = window.app.minigameScreen._gameInstance.deck; return ['2','3','4','5'].map(value => deck.findIndex(card => card.value === value)); }")
                for index in indices:
                    ui.locator(f'.hc-card[data-index="{index}"]').click()
                wait(frame, '() => { const game = window.app.minigameScreen._gameInstance; return game.currentPlayer === 1 && game.flippedThisTurn.length > 0; }')
                wait(frame, '() => { const game = window.app.minigameScreen._gameInstance; return game.currentPlayer === 0 && !game.turnLocked; }')
                frame.evaluate("() => { const screen = window.app.minigameScreen; window.previousBattleEnd = screen._gameInstance.onEnd; window.previousCaptureEnd = screen._currentCtx.onEnd; }")
                frame.evaluate('() => window.app.gameManager.reset()')

                # Mashing uses actual timed presses; human L cannot press for the bot.
                capture(frame, ui, 'mashing-battle')
                # Late completions from a previous game cannot resolve this capture.
                assert frame.evaluate("() => { const app = window.app; const game = app.minigameScreen._gameInstance; const pending = app.gameManager.pendingMove; window.previousBattleEnd({attackerWins:true}); window.previousCaptureEnd({attackerWins:true}); return app.minigameScreen._gameInstance === game && app.gameManager.pendingMove === pending && app.gameManager.state === 'MINIGAME'; }")
                wait(frame, '() => window.app.minigameScreen._gameInstance.position < 4')
                assert frame.evaluate("() => { const game = window.app.minigameScreen._gameInstance; const before = game.p2Presses; game._onKeyDown({key:'l', repeat:false}); return game.p2Presses === before; }")
                frame.evaluate('() => { const game = window.app.minigameScreen._gameInstance; game.position = 0; game.timeLeft = 0.1; }')
                finish(ui)

                # Timing AI waits for the real NOW cue and records a reaction.
                capture(frame, ui, 'timing-battle')
                frame.evaluate('() => { window.app.minigameScreen._gameInstance.position = 1; }')
                wait(frame, '() => { const game = window.app.minigameScreen._gameInstance; return game && game.p2Time !== null; }', timeout=10000)
                finish(ui)

                # Dodging bot moves away from a visible incoming hazard.
                capture(frame, ui, 'dodging-battle')
                frame.evaluate("() => { const game = window.app.minigameScreen._gameInstance; game.projectiles = [{x:280, y:110, vx:0, vy:120}]; game.spawnTimer = -100; }")
                wait(frame, '() => { const game = window.app.minigameScreen._gameInstance; return Math.hypot(game.p2.x - 280, game.p2.y - 200) > 10; }')
                frame.evaluate("() => { const game = window.app.minigameScreen._gameInstance; game.projectiles = [{x:game.p1.x, y:game.p1.y, vx:0, vy:0}]; }")
                finish(ui)

                # Restart cancels pending AI work; a local game never moves by itself.
                fixture(frame, None, human='b')
                frame.evaluate('() => window.app.gameManager.reset()')
                page.wait_for_timeout(1500)
                assert frame.evaluate("() => { const m = window.app.gameManager; return m.state === 'SETUP' && m.chess.history().length === 0; }")
                frame.evaluate("() => window.app.eventBus.emit('showSetup')")
                ui.locator('#btn-2p').click()
                expect(ui.locator('.setup-name-input')).to_have_count(2)
                ui.locator('#btn-next-profiles').click()
                ui.locator('#btn-next-minigames').click()
                move(ui, 'e2', 'e4')
                move(ui, 'e7', 'e5')
                page.wait_for_timeout(1000)
                assert frame.evaluate('() => window.app.gameManager.chess.history().length === 2')
                assert frame.evaluate('() => !window.app.gameManager.config.players.some(player => player.isAI)')

                # Solo startup remains usable at phone widths.
                page.set_viewport_size({'width': 390, 'height': 844})
                frame.evaluate("() => { window.app.gameManager.reset(); window.app.eventBus.emit('showSetup'); }")
                ui.locator('#btn-1p').click()
                expect(ui.locator('#chess-difficulty')).to_be_visible()
                expect(ui.locator('#ai-difficulty')).to_be_visible()
                assert ui.locator('.setup-panel').evaluate('element => element.getBoundingClientRect().width <= innerWidth')
                assert not errors, errors
                browser.close()
                print('PASS: solo setup, independent difficulties, both colors, AI captures/choice, five battle bots, cancellation, local multiplayer, and mobile setup; no browser errors.')
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    run()
