"""Compare real local/online battle artwork and responsive layouts.

Uses temporary databases only. Set BATTLE_CHESS_VISUAL_DIR to retain screenshots.
"""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from battle_chess_browser import QuietHandler
from test_site_theme import isolated_app

GAMES = ['highest-card', 'memory-match', 'mashing-battle', 'timing-battle', 'dodging-battle']
MOVES = [('e2', 'e4'), ('d7', 'd5'), ('b1', 'c3'), ('d5', 'e4')]


def run():
    with tempfile.TemporaryDirectory(prefix='chess-online-presentation-') as directory:
        app, _ = isolated_app(directory)
        from models import battle_chess as rooms
        output = Path(os.environ.get('BATTLE_CHESS_VISUAL_DIR', str(Path(directory) / 'screenshots')))
        output.mkdir(parents=True, exist_ok=True)
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = p.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
                pages = [browser.new_page(viewport={'width': 1280, 'height': 1000}) for _ in range(2)]
                errors = []
                for page in pages:
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(origin + '/games/battle-chess')
                    page.frame_locator('iframe').get_by_role('button', name='Play Online').wait_for()
                online_page, local_page = pages
                online, local = [next(f for f in page.frames if '/static/games/battle-chess/' in f.url) for page in pages]
                for viewport, size in [('desktop', {'width': 1280, 'height': 1000}), ('phone', {'width': 390, 'height': 844})]:
                    for page in pages:
                        page.set_viewport_size(size)
                    for game in GAMES:
                        state, white = rooms.create_room('White commander', {'mode': game, 'advantage': 'attacker'})
                        code = state['code']
                        state, black = rooms.join_room(code, 'Black commander')
                        for index, (source, target) in enumerate(MOVES):
                            state = rooms.act(code, white if index % 2 == 0 else black,
                                dict(id=uuid.uuid4().hex, version=state['version'], type='move', **{'from': source, 'to': target}))
                        if game in GAMES[2:]:
                            now = time.time()
                            with rooms._locked_room(code) as (_, room):
                                battle = room['battle']
                                battle.update(phase='playing', startAt=now - 1, lastTick=now,
                                              lastSeen={'w': now + 600, 'b': now + 600})
                                if game == 'mashing-battle':
                                    battle['endsAt'] = now + 20
                                elif game == 'timing-battle':
                                    rooms.minigames._timing_round(battle, now)
                                    battle['cueAt'] = now + 600
                                else:
                                    battle['spawnTimer'] = -600
                        online.evaluate("""async ({code, token, game}) => {
                            const network = app.onlineMultiplayer;
                            network._disconnect(false);
                            network._stored('battle-chess-explained:' + game, '1');
                            network._connect(code, token);
                            await network._sync();
                            network._schedule();
                        }""", {'code': code, 'token': black, 'game': game})
                        local.evaluate("""game => {
                            app.minigameScreen._hide();
                            app.gameManager.startGame({
                                playerCount: 2, selectedMinigames: [game], minigameAdvantage: 'attacker',
                                players: [{name:'White commander', color:'w'}, {name:'Black commander', color:'b'}]
                            });
                            for (const [from,to] of [['e2','e4'], ['d7','d5'], ['b1','c3'], ['d5','e4']]) app.gameManager.attemptMove(from,to);
                        }""", game)
                        got_it = local.get_by_role('button', name='Got It', exact=True)
                        if got_it.count():
                            got_it.click()
                        local.evaluate("""() => {
                            const game = app.minigameScreen._gameInstance;
                            game.clearTimers();
                            cancelAnimationFrame(game._animFrameId);
                            game._animFrameId = null;
                            if (game.id === 'mashing-battle') Object.assign(game, {running:true, countdownValue:-1, timeLeft:20});
                            if (game._draw) game._draw();
                        }""")
                        for mode, frame in [('online', online), ('local', local)]:
                            panel = frame.locator('.mg-screen')
                            expect(panel).to_be_visible()
                            expect(panel.locator('.mg-player-name')).to_have_text(['White commander', 'Black commander'])
                            expect(panel.locator('.mg-sidebar .player-emblem')).to_have_count(2)
                            expect(panel.locator('.mg-sidebar-right .mg-advantage-badge')).to_be_visible()
                            assert panel.evaluate('el => el.scrollWidth <= el.clientWidth + 1'), (viewport, game, mode, 'horizontal overflow')
                            if game in GAMES[:2]:
                                expect(panel.locator('.hc-card-back')).to_have_count(52)
                                frame.wait_for_function("() => [...document.querySelectorAll('.hc-card-img')].every(image => image.complete && image.naturalWidth > 0)")
                                assert panel.locator('.hc-grid').evaluate('el => getComputedStyle(el).gridTemplateColumns.split(" ").length') == (7 if viewport == 'phone' else 13)
                            else:
                                canvas = panel.locator('canvas')
                                expect(canvas).to_be_visible()
                                assert canvas.evaluate('el => { const c = el.getBoundingClientRect(), a = document.querySelector(".mg-arena").getBoundingClientRect(); return c.width > 150 && c.height > 100 && c.left >= a.left - 1 && c.right <= a.right + 1 && c.bottom <= a.bottom + 1; }'), (viewport, game, mode, 'canvas clipped')
                            panel.screenshot(path=str(output / f'{viewport}-{mode}-{game}.png'))
                        assert online.evaluate('() => { const game = app.onlineMultiplayer.battleScreen.game; return game._timers.size === 0 && game._animFrameId === null; }'), 'Network views must not run local game rules or timers'
                        assert online.locator('#battle-leave').evaluate('el => el.getBoundingClientRect().bottom <= innerHeight'), (viewport, game, 'leave clipped')
                        print('PASS:', viewport, game, 'local/online artwork, crests, Black attacker and layout', flush=True)
                # The online wrapper stays in the native fullscreen surface too.
                online.evaluate('() => { app.onlineMultiplayer._disconnect(false); app.overlay.classList.remove("active"); }')
                online_page.set_viewport_size({'width': 1100, 'height': 650})
                online.locator('#toggle-fullscreen').click()
                online.wait_for_function("() => document.fullscreenElement?.id === 'game-surface'")
                online.evaluate("""async ({code, token}) => {
                    const n = app.onlineMultiplayer; n._connect(code, token); await n._sync(); n._schedule();
                }""", {'code': code, 'token': black})
                expect(online.locator('.online-battle-screen')).to_be_visible()
                assert online.evaluate('() => document.fullscreenElement.contains(document.querySelector(".online-battle-screen"))')
                assert online.locator('#battle-leave').evaluate('el => el.getBoundingClientRect().bottom <= innerHeight')
                assert not errors, errors
                browser.close()
                print('PASS: all five local/online presentations on desktop and phone, native online fullscreen; no browser errors.')
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    run()
