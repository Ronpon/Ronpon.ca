"""Focused real-browser checks for commander crests and profile selection.

Run: .venv/Scripts/python.exe tests/battle_chess_profiles_browser.py
Uses temporary local databases by default. --url only exercises local browser
games on an existing deployment; it never creates rooms or changes account data.
--static-root serves a staged checkout's Battle Chess assets through the test app.
"""
import argparse
from pathlib import Path
import re
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server
from battle_chess_ai_browser import QuietHandler, move
from test_site_theme import isolated_app


def profile(ui, player):
    return ui.locator(f'.setup-profile[data-player="{player}"]')


def assert_choice(ui, player, icon, label):
    card = profile(ui, player)
    pressed = card.locator('.setup-icon-btn[aria-pressed="true"]')
    expect(pressed).to_have_count(1)
    expect(pressed).to_have_attribute('data-icon', icon)
    expect(card.locator('.setup-icon-btn.selected')).to_have_count(1)
    expect(card.locator('.setup-crest-preview > svg.player-emblem')).to_have_attribute('data-icon', icon)
    expect(card.locator('.setup-crest-name')).to_have_text(label)


def assert_fit(frame, ui):
    """Profile content may scroll vertically; controls must fit without clipping sideways."""
    frame.wait_for_function("""() => {
        const panel = document.querySelector('.player-setup-panel');
        if (!panel) return false;
        const rect = panel.getBoundingClientRect();
        return rect.left >= -1 && rect.top >= -1 && rect.right <= innerWidth + 1
            && rect.bottom <= innerHeight + 1 && panel.scrollWidth <= panel.clientWidth + 1
            && [...panel.querySelectorAll('.setup-icon-grid')].every(grid => grid.scrollWidth <= grid.clientWidth + 1)
            && document.documentElement.scrollWidth <= innerWidth + 1;
    }""")
    # Reach the final crest and Continue through the panel's own scrolling.
    for control in (ui.locator('.setup-icon-btn').last, ui.locator('#btn-next-profiles')):
        control.scroll_into_view_if_needed()
        expect(control).to_be_visible()
        # The existing 700px iframe can itself extend below a short parent page;
        # measure the control against its scrollable panel, not that outer page.
        assert control.evaluate("""element => {
            const rect = element.getBoundingClientRect();
            const panel = element.closest('.player-setup-panel').getBoundingClientRect();
            return rect.top >= panel.top - 1 && rect.bottom <= panel.bottom + 1;
        }""")


def show_capture(frame, ui, game):
    frame.evaluate("""game => {
        const app = window.app;
        app.gameManager.config.selectedMinigames = [game];
        app.gameManager.config.minigameMode = 'random';
        app.gameManager.chess.load('4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1');
        app.gameManager.setState('PLAYING');
        app.eventBus.emit('boardUpdated', app.gameManager.getGameState());
    }""", game)
    move(ui, 'e4', 'd5')
    expect(ui.locator('.mg-screen')).to_be_visible()
    got_it = ui.get_by_role('button', name='Got It', exact=True)
    if got_it.is_visible():
        got_it.click()


def exercise(url):
    with sync_playwright() as playwright:
        edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
        page = browser.new_page(viewport={'width': 1366, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(url)
            ui = page.frame_locator('iframe')
            ui.locator('#btn-2p').click()
            frame = next(frame for frame in page.frames if '/static/games/battle-chess/' in frame.url)

            # Two independent native button groups show named original SVG crests.
            for player in (0, 1):
                buttons = profile(ui, player).locator('.setup-icon-btn')
                expect(buttons).to_have_count(16)
                expect(buttons.locator('svg')).to_have_count(16)
                assert buttons.evaluate_all("buttons => buttons.every(button => button.tagName === 'BUTTON' && button.type === 'button' && /^[A-Za-z]/.test(button.getAttribute('aria-label')))")
            white = profile(ui, 0).locator('.setup-icon-btn').nth(11)
            black = profile(ui, 1).locator('.setup-icon-btn').nth(15)
            icons = [white.get_attribute('data-icon'), black.get_attribute('data-icon')]
            labels = [white.get_attribute('aria-label'), black.get_attribute('aria-label')]
            original_black = profile(ui, 1).locator('.setup-icon-btn[aria-pressed="true"]').get_attribute('data-icon')
            white.focus()
            white.press('Space')
            assert_choice(ui, 0, icons[0], labels[0])
            expect(profile(ui, 1).locator('.setup-icon-btn[aria-pressed="true"]')).to_have_attribute('data-icon', original_black)
            black.focus()
            black.press('Enter')
            assert_choice(ui, 0, icons[0], labels[0])
            assert_choice(ui, 1, icons[1], labels[1])

            # Saved names remain literal text, and both directions of Back retain choices.
            names = ['<img src=x>', 'Moon Keeper']
            profile(ui, 0).locator('.setup-name-input').fill(names[0])
            profile(ui, 1).locator('.setup-name-input').fill(names[1])
            ui.locator('#btn-next-profiles').click()
            ui.locator('#btn-back-profiles').click()
            for player in (0, 1):
                expect(profile(ui, player).locator('.setup-name-input')).to_have_value(names[player])
                assert_choice(ui, player, icons[player], labels[player])
            ui.locator('#btn-back-count').click()
            ui.locator('#btn-2p').click()
            for player in (0, 1):
                expect(profile(ui, player).locator('.setup-name-input')).to_have_value(names[player])
                assert_choice(ui, player, icons[player], labels[player])
            expect(ui.locator('img[src="x"]')).to_have_count(0)

            # The selector fits all themes, a short PC window, and the narrow iframe.
            for style in ('classic', 'fantasy', 'elven'):
                frame.evaluate('style => window.app.boardAppearance.setStyle(style)', style)
                assert_fit(frame, ui)
                assert_choice(ui, 0, icons[0], labels[0])
                assert_choice(ui, 1, icons[1], labels[1])
            page.set_viewport_size({'width': 1024, 'height': 600})
            assert_fit(frame, ui)
            fullscreen = ui.locator('#toggle-fullscreen')
            if fullscreen.count() and fullscreen.is_enabled():
                # Enter through the unobscured board button, then reopen setup as
                # a game returning to its profiles while already fullscreen would.
                frame.evaluate('() => window.app.setupWizard.hide()')
                fullscreen.click()
                frame.wait_for_function("() => document.fullscreenElement?.id === 'game-surface'")
                frame.evaluate('() => window.app.setupWizard._showPlayerProfiles()')
                assert_fit(frame, ui)
                fullscreen.click()
                frame.wait_for_function('() => !document.fullscreenElement')
            page.set_viewport_size({'width': 390, 'height': 844})
            assert_fit(frame, ui)
            assert profile(ui, 1).bounding_box()['y'] > profile(ui, 0).bounding_box()['y']
            page.set_viewport_size({'width': 1366, 'height': 900})

            # Start a real two-human game with the selected profiles and capture a piece.
            ui.locator('#btn-next-profiles').click()
            ui.locator('.setup-mg-check[data-id="highest-card"]').check()
            ui.locator('#btn-next-minigames').click()
            ui.locator('#adv-none').click()
            ui.locator('#rule-no').click()
            frame.evaluate("() => window.app.boardAppearance.setStyle('classic')")
            assert frame.evaluate('() => window.app.gameManager.config.players.map(player => player.icon)') == icons
            show_capture(frame, ui, 'highest-card')
            for player, side in ((0, 'left'), (1, 'right')):
                expect(ui.locator(f'.mg-sidebar-{side} .mg-player-icon svg.player-emblem')).to_have_attribute('data-icon', icons[player])
                expect(ui.locator(f'.mg-sidebar-{side} .mg-player-name')).to_have_text(names[player])
            frame.evaluate('() => window.app.minigameScreen._gameInstance.deck.forEach((card, index) => card.rank = index)')
            ui.locator('.hc-card').nth(0).click()
            ui.locator('.hc-card').nth(1).click()
            ui.get_by_role('button', name='Reveal', exact=True).click()
            expect(ui.locator('.hc-reveal-card')).to_have_count(2)
            assert frame.evaluate("() => [...document.querySelectorAll('.hc-reveal-card')].map(card => card.parentElement.querySelector('svg.player-emblem')?.dataset.icon)") == icons
            expect(ui.locator('img[src="x"]')).to_have_count(0)
            expect(ui.locator('.mg-continue-btn')).to_be_visible(timeout=10000)
            expect(ui.locator('.mg-result-icon svg.player-emblem')).to_have_attribute('data-icon', icons[1])
            ui.locator('.mg-continue-btn').click()

            # Canvas minigames consume the same profile values and draw their crests.
            show_capture(frame, ui, 'mashing-battle')
            expect(ui.locator('#mg-arena canvas')).to_be_visible()
            assert frame.evaluate("""() => {
                const game = window.app.minigameScreen._gameInstance;
                game._draw();
                const pixels = game.ctx.getImageData(0, 0, game.canvas.width, game.canvas.height).data;
                return pixels.some((value, index) => index % 4 === 3 && value > 0);
            }""")
            assert frame.evaluate('() => window.app.minigameScreen._gameInstance.players.map(player => player.icon)') == icons
            frame.evaluate('() => { window.app.gameManager.reset(); window.app.setupWizard.show(); }')

            # A solo human can play Black while White retains its fixed automaton.
            ui.locator('#btn-1p').click()
            ui.locator('#human-color').select_option('b')
            ui.locator('#btn-next-solo').click()
            computer = profile(ui, 0)
            human = profile(ui, 1)
            expect(computer).to_have_class(re.compile(r'\bsetup-computer-profile\b'))
            expect(computer.locator('.setup-name-input, .setup-icon-btn')).to_have_count(0)
            expect(computer.locator('.setup-computer-name')).to_have_text('Computer')
            expect(computer.locator('.setup-crest-preview svg.player-emblem')).to_have_attribute('data-icon', '🤖')
            expect(human.locator('.setup-icon-btn')).to_have_count(16)
            solo_choice = human.locator('.setup-icon-btn').nth(1)
            solo_icon = solo_choice.get_attribute('data-icon')
            solo_label = solo_choice.get_attribute('aria-label')
            solo_choice.click()
            human.locator('.setup-name-input').fill('Black Knight')
            ui.locator('#btn-back-count').click()
            expect(ui.locator('#human-color')).to_have_value('b')
            ui.locator('#btn-next-solo').click()
            expect(human.locator('.setup-name-input')).to_have_value('Black Knight')
            assert_choice(ui, 1, solo_icon, solo_label)
            expect(computer.locator('.setup-crest-preview svg.player-emblem')).to_have_attribute('data-icon', '🤖')
            assert not errors, errors
            print('PASS: independent keyboard crest selection, live SVG previews, Back retention, safe names, three themes, short PC/fullscreen/mobile fit, real card capture/reveal/result and canvas drawing, and solo Black with a fixed computer crest; no browser errors.')
        finally:
            browser.close()


def run(url=None, static_root=None):
    if url:
        exercise(url)
        return
    with tempfile.TemporaryDirectory(prefix='battle-chess-profiles-') as directory:
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
