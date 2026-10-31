"""Two-browser checks for Memory, Mashing, Timing, Dodging, and game selection.

Run: .venv/Scripts/python.exe tests/battle_chess_minigames_browser.py
Requires Playwright plus Edge/Chromium. Uses temporary databases only.
"""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server
from battle_chess_browser import QuietHandler, move
from test_site_theme import isolated_app


def wait_value(frame, expression, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if frame.evaluate(expression):
            return
        frame.page.wait_for_timeout(100)
    raise AssertionError('Browser state did not converge: ' + expression)


def run():
    with tempfile.TemporaryDirectory(prefix='chess-minigames-') as directory:
        app, _ = isolated_app(directory)
        app.config['RATE_LIMIT_ENABLED'] = True
        from models import battle_chess as rooms
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
                errors = []
                for game in (sys.argv[1:] or ['memory-match', 'mashing-battle', 'timing-battle', 'dodging-battle', 'mixed']):
                    contexts = [browser.new_context(viewport={'width': 1100, 'height': 1000}) for _ in range(2)]
                    pages = [c.new_page() for c in contexts]
                    for page in pages:
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('response', lambda response: errors.append(f'{response.status}: {response.url}') if response.status >= 400 and '/battle-chess/api/' in response.url else None)
                    host, guest = pages
                    # Exercise controls while a previous response is still in flight.
                    delay = float(os.environ.get('BATTLE_CHESS_INPUT_DELAY_MS', '0')) / 1000
                    if delay:
                        def delayed_input(route):
                            response = route.fetch()
                            time.sleep(delay)
                            route.fulfill(response=response)
                        host.route('**/battle-input', delayed_input)
                    host.goto(origin + '/games/battle-chess')
                    h = host.frame_locator('iframe')
                    h.get_by_role('button', name='Play Online').click()
                    h.get_by_label('Your name', exact=True).fill('White player')
                    h.get_by_label('Capture battles').select_option(game)
                    h.get_by_label('Battle advantage').select_option('none')
                    if game == 'mixed':
                        h.get_by_label('Game selection').select_option('defenderChoice')
                    h.get_by_role('button', name='Create room', exact=True).click()
                    expect(h.locator('.online-room-code')).to_be_visible()
                    code = h.locator('.online-room-code').inner_text()
                    guest.goto(h.get_by_label('Invite link').input_value())
                    g = guest.frame_locator('iframe')
                    g.get_by_label('Your name', exact=True).fill('Black player')
                    g.get_by_role('button', name='Join room', exact=True).click()
                    expect(h.locator('#online-status')).to_contain_text('Black player connected', timeout=10000)
                    move(h, 'e2', 'e4')
                    expect(g.locator('#turn-indicator')).to_contain_text('Black', timeout=10000)
                    move(g, 'd7', 'd5')
                    expect(h.locator('#turn-indicator')).to_contain_text('White', timeout=10000)
                    move(h, 'e4', 'd5')
                    expect(g.locator('#online-battle-status')).to_be_visible(timeout=10000)
                    hf = next(f for f in host.frames if '/static/games/battle-chess/' in f.url)
                    gf = next(f for f in guest.frames if '/static/games/battle-chess/' in f.url)
                    if game == 'mixed':
                        expect(h.get_by_role('button', name='Memory Match', exact=True)).to_be_disabled()
                        g.get_by_role('button', name='Memory Match', exact=True).click()
                        expect(h.get_by_role('heading', name='Memory Match', exact=True)).to_be_visible(timeout=10000)
                        h.locator('#battle-leave').click()
                        h.get_by_role('button', name='Confirm', exact=True).click()
                        expect(g.locator('#online-result')).to_contain_text('left the room', timeout=10000)
                    elif game == 'memory-match':
                        for frame in (h, g):
                            frame.get_by_role('button', name='Got It', exact=True).click()
                            expect(frame.locator('.hc-card-back img')).to_have_count(52)
                        with rooms._locked_room(code) as (_, room):
                            room['battle']['deck'] = list(range(52))
                        expect(g.get_by_role('button', name='Flip card 1', exact=True)).to_be_disabled()
                        h.get_by_role('button', name='Flip card 1', exact=True).click()
                        expect(g.get_by_role('button', name='Card 1: 2♠', exact=True)).to_be_visible(timeout=10000)
                        guest.reload()
                        expect(g.get_by_role('button', name='Card 1: 2♠', exact=True)).to_be_visible(timeout=10000)
                        for index in (14, 27, 40):
                            h.get_by_role('button', name=f'Flip card {index}', exact=True).click()
                    else:
                        for frame in (h, g):
                            expect(frame.locator('.mg-sidebar .player-emblem')).to_have_count(2)
                            expect(frame.locator('.online-game-surface canvas')).to_be_visible()
                        if game == 'dodging-battle':
                            # Keep random hazards out of the movement/reconnect check;
                            # inject a collision after both sets of controls are verified.
                            with rooms._locked_room(code) as (_, room):
                                room['battle']['spawnTimer'] = -10
                        h.get_by_role('button', name='Ready to battle', exact=True).click()
                        expect(h.get_by_role('button', name='Waiting for your opponent…', exact=True)).to_be_disabled()
                        g.get_by_role('button', name='Ready to battle', exact=True).click()
                        expect(h.locator('#online-battle-status')).to_contain_text('Starting in', timeout=10000)
                        if game == 'mashing-battle':
                            expect(h.locator('#battle-tap')).to_be_enabled(timeout=10000)
                            for _ in range(5):
                                h.locator('#battle-tap').click()
                            expect(g.locator('.online-reactions')).to_contain_text('White: 5 presses', timeout=10000)
                            # Exercise the other player's keyboard and ignore key repeats.
                            g.locator('#battle-tap').focus()
                            guest.keyboard.press('l')
                            expect(h.locator('.online-reactions')).to_contain_text('Black: 1 presses', timeout=10000)
                            expect(h.get_by_role('button', name='Return to board', exact=True)).to_be_visible(timeout=25000)
                        elif game == 'timing-battle':
                            with rooms._locked_room(code) as (_, room):
                                room['battle']['position'] = 7  # one full reaction round decides this fixture
                            expect(h.locator('#online-battle-status')).to_have_text('NOW!', timeout=15000)
                            h.locator('#battle-tap').click()
                            guest.wait_for_timeout(500)
                            g.locator('#battle-tap').click()
                            expect(h.locator('#online-battle-status')).to_contain_text('Attacker wins', timeout=10000)
                        else:
                            expect(h.locator('#online-battle-status')).to_have_text('Dodge! Keep away from the incoming projectiles.', timeout=10000)
                            h.locator('.online-dodge-canvas').click()
                            host.keyboard.down('d')
                            wait_value(gf, "() => window.app.onlineMultiplayer.room.battle.actors.w.x > 140")
                            host.keyboard.up('d')
                            contexts[1].set_offline(True)
                            expect(h.locator('#online-battle-status')).to_contain_text('battle is paused', timeout=10000)
                            contexts[1].set_offline(False)
                            guest.reload()
                            expect(g.get_by_role('button', name='Ready to resume', exact=True)).to_be_visible(timeout=10000)
                            h.get_by_role('button', name='Ready to resume', exact=True).click()
                            g.get_by_role('button', name='Ready to resume', exact=True).click()
                            expect(h.locator('#online-battle-status')).to_have_text('Dodge! Keep away from the incoming projectiles.', timeout=10000)
                            # Touch-sized direction controls also work in a mobile viewport.
                            guest.set_viewport_size({'width': 390, 'height': 844})
                            button = g.get_by_role('button', name='Move left', exact=True)
                            button.scroll_into_view_if_needed()
                            box = button.bounding_box()
                            guest.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                            guest.mouse.down()
                            wait_value(hf, "() => window.app.onlineMultiplayer.room.battle.actors.b.x < 260")
                            guest.mouse.up()
                            if os.environ.get('BATTLE_CHESS_SCREENSHOT'):
                                host.screenshot(path=os.environ['BATTLE_CHESS_SCREENSHOT'], full_page=True)
                                screenshot = Path(os.environ['BATTLE_CHESS_SCREENSHOT'])
                                guest.screenshot(path=str(screenshot.with_name(screenshot.stem + '-mobile.png')), full_page=True)
                            assert g.locator('.online-dodge-canvas').evaluate("el => el.getBoundingClientRect().top >= 0 && document.querySelector('.online-direction-pad').getBoundingClientRect().bottom <= innerHeight"), 'Mobile arena and controls should be visible together'
                            with rooms._locked_room(code) as (_, room):
                                # Under delayed responses the players may overlap.
                                # Isolate this targeted hit from the simultaneous-hit test.
                                room['battle']['actors']['w']['y'] = 50
                                room['battle']['actors']['b']['y'] = 350
                                actor = room['battle']['actors']['b']
                                room['battle']['projectiles'] = [dict(x=actor['x'], y=actor['y'], vx=0, vy=0)]
                            expect(h.locator('#online-battle-status')).to_contain_text('Attacker wins', timeout=10000)
                    if game != 'mixed':
                        expect(g.get_by_role('button', name='Return to board', exact=True)).to_be_visible(timeout=10000)
                        h.get_by_role('button', name='Return to board', exact=True).click()
                        g.get_by_role('button', name='Return to board', exact=True).click()
                        expect(h.locator('#overlay-container')).not_to_have_class('active', timeout=10000)
                        expect(g.locator('#turn-indicator')).to_contain_text('Black', timeout=10000)
                    for context in contexts:
                        context.close()
                    print('PASS:', game, flush=True)
                assert not errors, errors
                browser.close()
                print('PASS: selected online minigames; shared input, timers, refresh, pause/resume, mobile controls, and capture results; no browser/API errors.')
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    run()
