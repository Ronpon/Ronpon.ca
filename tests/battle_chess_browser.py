"""Optional real-browser integration check.

Run: .venv/Scripts/python.exe tests/battle_chess_browser.py
Requires Playwright and Microsoft Edge (or a Playwright Chromium installation).
Uses temporary databases and two independent browser contexts, never production.
"""
import os
from pathlib import Path
import tempfile
import threading
import sys

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


def run():
    with tempfile.TemporaryDirectory(prefix='battle-chess-browser-') as directory:
        app, _ = isolated_app(directory)
        from models import battle_chess as rooms
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
                contexts = [browser.new_context(viewport={'width': 1100, 'height': 1000}) for _ in range(3)]
                pages = [context.new_page() for context in contexts]
                errors = []
                for page in pages:
                    page.on('pageerror', lambda error: errors.append(str(error)))
                host, guest, outsider = pages
                host.goto(origin + '/games/battle-chess')
                h = host.frame_locator('iframe')
                h.get_by_role('button', name='Play Online').click()
                h.get_by_label('Your name', exact=True).fill('Alice <host>')
                h.get_by_role('button', name='Create room', exact=True).click()
                expect(h.get_by_role('heading', name='Waiting for your friend')).to_be_visible()
                code = h.locator('.online-room-code').inner_text()
                invite = h.get_by_label('Invite link').input_value()
                assert invite == origin + '/games/battle-chess?room=' + code
                guest.goto(invite)
                g = guest.frame_locator('iframe')
                expect(g.get_by_label('Room code')).to_have_value(code)
                g.get_by_label('Your name', exact=True).fill('Bob')
                g.get_by_role('button', name='Join room', exact=True).click()
                expect(h.locator('#online-status')).to_contain_text('Bob connected', timeout=10000)
                expect(g.locator('#online-status')).to_contain_text('You are Black')
                # Appearance is local: host uses Sylvan Court, guest keeps Runeforge.
                h.get_by_role('button', name='Elven 3D', exact=True).click()
                expect(h.get_by_role('heading', name='Sylvan Court')).to_be_visible()
                expect(g.get_by_role('heading', name='Runeforge')).to_be_visible()
                # Guest cannot move White, even by clicking White's pieces.
                move(g, 'e2', 'e4')
                expect(g.locator('#turn-indicator')).to_contain_text('White')
                move(h, 'e2', 'e4')
                expect(g.locator('#turn-indicator')).to_contain_text('Black', timeout=10000)
                move(g, 'd7', 'd5')
                expect(h.locator('#turn-indicator')).to_contain_text('White', timeout=10000)
                move(h, 'e4', 'd5')
                expect(g.get_by_role('heading', name='Highest Card', exact=True)).to_be_visible(timeout=10000)
                for frame in (h, g):
                    frame.get_by_role('button', name='Got It', exact=True).click()
                    expect(frame.locator('.mg-sidebar .player-emblem')).to_have_count(2)
                    expect(frame.locator('.hc-card-back img')).to_have_count(52)
                expect(g.get_by_role('button', name='Pick card 1', exact=True)).to_be_disabled()
                h.get_by_role('button', name='Pick card 1', exact=True).click()
                expect(g.get_by_role('button', name='Pick card 2', exact=True)).to_be_enabled(timeout=10000)
                # Refresh while a battle is pending: same seat, same choices.
                guest.reload()
                expect(g.get_by_role('button', name='Pick card 2', exact=True)).to_be_enabled(timeout=10000)
                g.get_by_role('button', name='Pick card 2', exact=True).click()
                expect(h.get_by_role('button', name='Reveal', exact=True)).to_be_visible(timeout=10000)
                h.get_by_role('button', name='Reveal', exact=True).click()
                expect(h.locator('.hc-reveal-card')).to_have_count(2, timeout=10000)
                if os.environ.get('BATTLE_CHESS_SCREENSHOT'):
                    host.screenshot(path=os.environ['BATTLE_CHESS_SCREENSHOT'], full_page=True)
                h.get_by_role('button', name='Return to board', exact=True).click()
                expect(g.get_by_role('button', name='Return to board', exact=True)).to_be_enabled(timeout=10000)
                g.get_by_role('button', name='Return to board', exact=True).click()
                expect(h.locator('#overlay-container')).not_to_have_class('active', timeout=10000)
                expect(g.locator('#turn-indicator')).to_contain_text('Black')
                # A third browser cannot take an occupied seat.
                outsider.goto(invite)
                third = outsider.frame_locator('iframe')
                third.get_by_label('Your name', exact=True).fill('Third player')
                third.get_by_role('button', name='Join room', exact=True).click()
                expect(third.locator('.online-message')).to_contain_text('full', timeout=10000)
                # Offline recovery brings in the opponent's move.
                contexts[0].set_offline(True)
                expect(h.locator('#online-status')).to_contain_text('Connection', timeout=15000)
                move(g, 'g8', 'f6')
                contexts[0].set_offline(False)
                expect(h.locator('#online-status')).to_contain_text('Bob connected', timeout=15000)
                expect(h.locator('#turn-indicator')).to_contain_text('White', timeout=10000)
                h.get_by_role('button', name='Resign', exact=True).click()
                h.get_by_role('button', name='Confirm', exact=True).click()
                expect(g.get_by_role('heading', name='Game Over', exact=True)).to_be_visible(timeout=10000)
                expect(g.locator('#online-result')).to_contain_text('Bob (Black) wins')
                h.get_by_role('button', name='Play again', exact=True).click()
                expect(g.get_by_role('button', name='Accept rematch', exact=True)).to_be_visible(timeout=10000)
                g.get_by_role('button', name='Accept rematch', exact=True).click()
                expect(h.locator('#turn-indicator')).to_contain_text('White', timeout=10000)
                expect(h.locator('#overlay-container')).not_to_have_class('active', timeout=10000)
                # A remote resignation must cancel a pending promotion dialog;
                # otherwise the input handler could stay locked through a rematch.
                with rooms._locked_room(code) as (_, room):
                    room['fen'] = '7k/P7/8/8/8/8/8/7K w - - 0 1'
                    room['positions'] = []
                    room['version'] += 1
                host_frame = next(frame for frame in host.frames if '/static/games/battle-chess/' in frame.url)
                for _ in range(50):
                    if host_frame.evaluate("() => window.app.gameManager.chess.fen().startsWith('7k/P7/')"):
                        break
                    host.wait_for_timeout(200)
                else:
                    raise AssertionError('Promotion fixture did not reach the host')
                move(h, 'a7', 'a8')
                expect(h.get_by_role('heading', name='Promote Pawn')).to_be_visible()
                g.get_by_role('button', name='Resign', exact=True).click()
                g.get_by_role('button', name='Confirm', exact=True).click()
                expect(h.get_by_role('heading', name='Game Over', exact=True)).to_be_visible(timeout=10000)
                h.get_by_role('button', name='Play again', exact=True).click()
                expect(g.get_by_role('button', name='Accept rematch', exact=True)).to_be_visible(timeout=10000)
                g.get_by_role('button', name='Accept rematch', exact=True).click()
                expect(h.locator('#overlay-container')).not_to_have_class('active', timeout=10000)
                move(h, 'e2', 'e4')
                expect(g.locator('#turn-indicator')).to_contain_text('Black', timeout=10000)
                h.get_by_role('button', name='Leave room', exact=True).click()
                h.get_by_role('button', name='Confirm', exact=True).click()
                expect(h.get_by_role('heading', name='How Many Players?')).to_be_visible()
                expect(h.locator('#btn-1p')).to_be_enabled()
                expect(g.locator('#online-result')).to_contain_text('left the room', timeout=10000)
                # Existing local setup still works after leaving online play.
                h.locator('#btn-2p').click()
                expect(h.locator('.setup-profile')).to_have_count(2)
                # Mobile lobby fits the iframe and classic mode disables battle rules.
                outsider.set_viewport_size({'width': 390, 'height': 844})
                outsider.goto(origin + '/games/battle-chess')
                third.get_by_role('button', name='Play Online').click()
                third.get_by_label('Your name', exact=True).fill('Mobile host')
                third.get_by_label('Capture battles').select_option('classic')
                expect(third.get_by_label('Battle advantage')).to_be_disabled()
                third.get_by_role('button', name='Create room', exact=True).click()
                expect(third.get_by_role('heading', name='Waiting for your friend')).to_be_visible()
                expect(third.locator('#online-rules')).to_contain_text('Classic chess')
                assert third.locator('.online-panel').evaluate('el => el.getBoundingClientRect().width <= innerWidth')
                third.locator('.online-panel').get_by_role('button', name='Leave room', exact=True).click()
                expect(third.get_by_role('heading', name='How Many Players?')).to_be_visible()
                assert not errors, errors
                browser.close()
                print('PASS: two-browser invites, seat ownership, synchronized moves, Highest Card, refresh, full room, offline recovery, resignation, rematch, promotion interruption, leave, local setup, and mobile classic lobby; no browser errors.')
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    run()
