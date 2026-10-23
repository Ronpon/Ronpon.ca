"""Real-browser checks for embedded fullscreen and bulk minigame selection.

Run: .venv/Scripts/python.exe tests/battle_chess_fullscreen_browser.py
Uses temporary local databases by default. --url checks a deployed game instead;
all chess fixtures remain in the browser and do not create online rooms.
"""
import argparse
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server
from battle_chess_ai_browser import QuietHandler, move
from test_site_theme import isolated_app


def fit(frame):
    frame.wait_for_function("""() => {
        const canvas = document.querySelector('#game-canvas:not([hidden]), #fantasy-canvas:not([hidden])');
        const rect = canvas.getBoundingClientRect();
        const surface = document.querySelector('#game-surface');
        return rect.width > 250 && Math.abs(rect.width - rect.height) < 2
            && rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth + 1 && rect.bottom <= innerHeight + 1
            && surface.scrollHeight <= surface.clientHeight + 1
            && surface.scrollWidth <= surface.clientWidth + 1
            && document.documentElement.scrollHeight <= innerHeight + 1
            && document.documentElement.scrollWidth <= innerWidth + 1;
    }""")
    assert frame.evaluate("""() => ['#toggle-fullscreen', '#info-panel'].every(selector => {
        const rect = document.querySelector(selector).getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= innerHeight && rect.left >= 0 && rect.right <= innerWidth;
    })""")


def load(frame, fen, games=()):
    frame.evaluate("""({fen, games}) => {
        const app = window.app;
        app.gameManager.config.selectedMinigames = games;
        app.gameManager.config.minigameMode = 'random';
        app.gameManager.chess.load(fen);
        app.gameManager.setState('PLAYING');
        app.eventBus.emit('boardUpdated', app.gameManager.getGameState());
    }""", {'fen': fen, 'games': list(games)})


def exercise(origin):
    with sync_playwright() as playwright:
        edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
        page = browser.new_page(viewport={'width': 1366, 'height': 768})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin)
        ui = page.frame_locator('iframe')
        ui.locator('#btn-2p').click()
        ui.locator('#btn-next-profiles').click()
        all_games = ui.get_by_label('Select all minigames', exact=True)
        expect(all_games).not_to_be_checked()
        expect(ui.locator('.setup-mode-btn').first).to_be_disabled()
        all_games.check()
        count = ui.locator('.setup-mg-check').count()
        assert count == 5
        expect(ui.locator('.setup-mg-check:checked')).to_have_count(count)
        expect(ui.locator('.setup-mode-btn').first).to_be_enabled()
        ui.locator('.setup-mg-check').first.uncheck()
        assert all_games.evaluate('element => element.indeterminate && !element.checked')
        all_games.check()
        expect(ui.locator('.setup-mg-check:checked')).to_have_count(count)
        all_games.uncheck()
        expect(ui.locator('.setup-mg-check:checked')).to_have_count(0)
        expect(ui.locator('.setup-mode-btn').first).to_be_disabled()
        all_games.check()
        ui.locator('.setup-mode-btn[data-mode="setOrder"]').click()
        ui.locator('#btn-back-profiles').click()
        ui.locator('#btn-next-profiles').click()
        expect(all_games).to_be_checked()
        expect(ui.locator('.setup-mode-btn[data-mode="setOrder"]')).to_have_class('btn setup-mode-btn active')
        ui.locator('#btn-next-minigames').click()
        ui.locator('#adv-none').click()
        ui.locator('#rule-no').click()
        frame = next(frame for frame in page.frames if '/static/games/battle-chess/' in frame.url)
        assert frame.evaluate('() => window.app.gameManager.config.selectedMinigames.length === 5')

        # Native fullscreen escapes the surrounding page and the fixed-height iframe.
        ui.locator('#view-classic').click()
        ui.locator('#toggle-fullscreen').click()
        frame.wait_for_function("() => document.fullscreenElement?.id === 'game-surface'")
        expect(ui.locator('#toggle-fullscreen')).to_have_text('Exit full screen')
        fit(frame)
        assert frame.evaluate("() => document.querySelector('#game-canvas').width === 640")
        move(ui, 'e2', 'e4')
        assert frame.evaluate("() => window.app.gameManager.chess.get('e4')?.type === 'p'")

        # Changing view and resizing retain a playable square board without scrolling.
        ui.locator('#view-fantasy').click()
        fit(frame)
        move(ui, 'e7', 'e5')
        ui.locator('#view-elven').click()
        fit(frame)
        move(ui, 'g1', 'f3')
        assert frame.evaluate("() => window.app.gameManager.chess.get('f3')?.type === 'n'")
        page.set_viewport_size({'width': 1024, 'height': 600})
        fit(frame)
        ui.locator('[data-view="top"]').click()
        ui.locator('[data-view="in"]').click()
        fit(frame)
        outer_scroll = page.evaluate('scrollY')
        ui.locator('#fantasy-canvas').hover()
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(100)
        assert page.evaluate('scrollY') == outer_scroll
        assert frame.evaluate('scrollY') == 0

        # Capture overlays and promotion remain inside the fullscreen element.
        ui.locator('#view-classic').click()
        load(frame, '4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1', ['highest-card'])
        move(ui, 'e4', 'd5')
        expect(ui.locator('.mg-screen')).to_be_visible()
        assert frame.evaluate("() => document.fullscreenElement.contains(document.querySelector('.mg-screen'))")
        expect(ui.locator('#toggle-fullscreen')).to_be_visible()
        ui.get_by_role('button', name='Got It', exact=True).click()
        frame.evaluate('() => window.app.minigameScreen._gameInstance.deck.forEach((card,index) => card.rank=index)')
        ui.locator('.hc-card').nth(0).click()
        ui.locator('.hc-card').nth(1).click()
        ui.get_by_role('button', name='Reveal', exact=True).click()
        ui.locator('.mg-continue-btn').click(timeout=10000)
        expect(ui.locator('.mg-screen')).to_have_count(0)
        fit(frame)
        load(frame, '4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        move(ui, 'a7', 'a8')
        expect(ui.locator('.promotion-choices')).to_be_visible()
        ui.locator('.promotion-btn[data-piece="q"]').click()
        assert frame.evaluate("() => window.app.gameManager.chess.get('a8')?.type === 'q'")
        fit(frame)

        # Both explicit exit and browser exits restore the embedded layout.
        ui.locator('#toggle-fullscreen').click()
        frame.wait_for_function('() => !document.fullscreenElement')
        expect(ui.locator('#toggle-fullscreen')).to_have_text('Full screen')
        ui.locator('#toggle-fullscreen').click()
        frame.wait_for_function("() => document.fullscreenElement?.id === 'game-surface'")
        page.keyboard.press('Escape')
        frame.wait_for_function('() => !document.fullscreenElement')
        expect(ui.locator('#game-surface')).not_to_have_class('fullscreen-active')
        ui.locator('#toggle-fullscreen').click()
        frame.wait_for_function("() => document.fullscreenElement?.id === 'game-surface'")
        fit(frame)
        ui.locator('#toggle-fullscreen').click()
        frame.wait_for_function('() => !document.fullscreenElement')

        # A denied browser request reports failure and leaves the board usable.
        frame.evaluate("() => { document.querySelector('#game-surface').requestFullscreen = () => Promise.reject(new Error('Test denial')); }")
        ui.locator('#toggle-fullscreen').click()
        expect(ui.locator('#toggle-fullscreen')).to_be_enabled()
        expect(ui.locator('#toggle-fullscreen')).to_have_text('Full screen')
        expect(ui.locator('#fullscreen-message')).to_contain_text('could not open')
        assert frame.evaluate('() => !document.fullscreenElement')
        assert not errors, errors
        browser.close()
        print('PASS: select all/none/partial selection, Back retention, native iframe fullscreen, square scroll-free boards, legal moves in all three views, short PC viewport, camera controls, capture battle, promotion, exits/re-entry, and denied request; no browser errors.')


def run(url=None, static_root=None):
    if url:
        exercise(url)
        return
    with tempfile.TemporaryDirectory(prefix='battle-chess-fullscreen-') as directory:
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
