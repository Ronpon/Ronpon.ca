"""Runeforge rendering/input/export regression checks using installed Edge/Playwright.

Run: .venv/Scripts/python.exe tests/battle_chess_fantasy_browser.py
Serves only static files; never touches application databases.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import sys
import threading

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ELVEN = '--elven' in sys.argv
THEME = 'elven' if ELVEN else 'runeforge'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/static/games/battle-chess/index.html'
    output = ROOT / 'prototypes/.qa' / THEME
    output.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
            browser = p.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
            page = browser.new_page(viewport={'width': 1100, 'height': 1200}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(url)
            page.wait_for_function('window.app?.setupWizard && window.app.board.fantasyActive', timeout=60000)
            page.evaluate('app.setupWizard.hide(); app.gameManager.startGame({selectedMinigames: []})')
            if ELVEN:
                page.get_by_role('button', name='Elven 3D', exact=True).click()
            assert page.evaluate('app.board.fantasy.theme') == THEME
            expect(page.locator('#fantasy-canvas')).to_be_visible()
            assert page.evaluate('app.board.fantasy.pieces.children.length') == 32
            # Verify the actual raster asset loads behind a transparent renderer.
            assert page.evaluate('''async theme => {
                const css = getComputedStyle(document.getElementById('canvas-container')).backgroundImage;
                if (!css.includes(theme === 'elven' ? 'elven-sanctuary.png' : 'runeforge-forge.png')) return false;
                const image = new Image();
                image.src = css.slice(5, -2);
                await image.decode();
                return image.naturalWidth >= 1024 && image.naturalHeight >= 1024
                    && app.board.fantasy.renderer.getClearAlpha() === 0
                    && !app.board.fantasy.environment;
            }''', THEME)
            page.screenshot(path=str(output / 'desktop.png'), full_page=True)

            def click_square(square):
                point = page.evaluate('(sq) => app.board.fantasy.squareToScreen(sq)', square)
                page.locator('#fantasy-canvas').click(position=point)

            def move(source, target):
                click_square(source)
                assert page.evaluate('app.inputHandler.selectedSquare') == source, source
                click_square(target)
                page.wait_for_timeout(350)
                assert page.evaluate('(sq) => app.gameManager.chess.get(sq)', target), target

            # Actual primary-button dragging preserves selection and cannot make a move.
            click_square('e2')
            initial_fen = page.evaluate('app.gameManager.chess.fen()')
            canvas_rect = page.locator('#fantasy-canvas').bounding_box()
            pawn = page.evaluate('app.board.fantasy.squareToScreen("e2")')
            px, py = canvas_rect['x'] + pawn['x'], canvas_rect['y'] + pawn['y']
            page.mouse.move(px, py)
            page.mouse.down()
            page.mouse.move(px + 85, py - 40, steps=8)
            page.mouse.up()
            assert page.evaluate('app.board.fantasy.yaw') < -.4
            assert page.evaluate('app.board.fantasy.elevation') > 1.0
            assert page.evaluate('app.inputHandler.selectedSquare') == 'e2'
            assert page.evaluate('app.gameManager.chess.fen()') == initial_fen
            assert page.evaluate('app.board.fantasy.drag') is None
            page.get_by_role('button', name='Reset', exact=True).click()
            click_square('e2')
            assert page.evaluate('app.inputHandler.selectedSquare') is None

            # Small hand jitter remains a click; dragging outside the canvas releases cleanly.
            page.mouse.move(px, py)
            page.mouse.down()
            page.mouse.move(px + 2, py + 1)
            page.mouse.up()
            assert page.evaluate('app.inputHandler.selectedSquare') == 'e2'
            page.mouse.move(px, py)
            page.mouse.down(button='right')
            page.mouse.move(canvas_rect['x'] - 20, py, steps=6)
            page.mouse.up(button='right')
            assert page.evaluate('app.board.fantasy.drag') is None
            assert page.evaluate('app.inputHandler.selectedSquare') == 'e2'
            page.get_by_role('button', name='Reset', exact=True).click()
            click_square('e2')

            # Cancelled input never leaves the board stuck in dragging mode.
            page.mouse.move(px, py)
            page.mouse.down()
            page.mouse.move(px + 30, py, steps=3)
            page.evaluate('''() => {
                const board = app.board.fantasy;
                board.canvas.dispatchEvent(new PointerEvent('pointercancel', {pointerId: board.drag.id}));
            }''')
            page.mouse.up()
            assert page.evaluate('app.board.fantasy.drag') is None
            assert page.locator('#fantasy-canvas').evaluate('(canvas) => !canvas.classList.contains("is-dragging")')
            page.get_by_role('button', name='Reset', exact=True).click()

            move('e2', 'e4')
            assert page.evaluate('app.gameManager.chess.turn()') == 'b'
            page.get_by_role('button', name='Flip', exact=True).click()
            move('d7', 'd5')
            move('e4', 'd5')
            assert page.evaluate('app.board.fantasy.pieces.children.length') == 31
            page.get_by_role('button', name='Top view', exact=True).click()
            move('g8', 'f6')
            fen = page.evaluate('app.gameManager.chess.fen()')
            page.get_by_role('button', name='Classic 2D', exact=True).click()
            expect(page.locator('#game-canvas')).to_be_visible()
            assert page.evaluate('app.gameManager.chess.fen()') == fen
            canvas = page.locator('#game-canvas')
            size = canvas.bounding_box()['width']
            for col, row in [(6, 7), (5, 5)]:
                canvas.click(position={'x': (col + .5) * size / 8, 'y': (row + .5) * size / 8})
            assert page.evaluate('app.gameManager.chess.get("f3").type') == 'n'
            page.get_by_role('button', name='Runeforge 3D', exact=True).click()
            if ELVEN:
                switched_fen = page.evaluate('app.gameManager.chess.fen()')
                page.get_by_role('button', name='Elven 3D', exact=True).click()
                assert page.evaluate('app.gameManager.chess.fen()') == switched_fen
            expect(page.locator('#fantasy-canvas')).to_be_visible()
            page.get_by_role('button', name='Reset', exact=True).click()

            def load(fen):
                page.evaluate('''fen => {
                    app.gameManager.chess.load(fen);
                    app.gameManager.state = 'PLAYING';
                    app.eventBus.emit('boardUpdated', app.gameManager.getGameState());
                }''', fen)

            load('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
            move('e1', 'g1')
            assert page.evaluate('app.gameManager.chess.get("f1").type') == 'r'
            assert page.evaluate('app.board.fantasy.pieces.children.some(p => p.userData.square === "f1")')
            load('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1')
            move('e5', 'd6')
            assert page.evaluate('app.gameManager.chess.get("d5")') is None
            assert page.evaluate('app.board.fantasy.pieces.children.length') == 3
            load('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
            click_square('a7')
            click_square('a8')
            expect(page.locator('.promotion-choices')).to_be_visible()
            page.locator('.promotion-btn[data-piece="q"]').click()
            page.wait_for_timeout(350)
            assert page.evaluate('app.gameManager.chess.get("a8").type') == 'q'
            load('4k3/8/8/8/8/8/4r3/4K3 w - - 0 1')
            assert page.evaluate('app.board.checkSquare') == 'e1'

            page.evaluate('app.gameManager.startGame({selectedMinigames: []})')
            with page.expect_download() as download:
                page.get_by_role('button', name='Download 3D set').click()
            filename = 'sylvan-court-chess-set.glb' if ELVEN else 'runeforge-chess-set.glb'
            assert download.value.suggested_filename == filename
            asset = ROOT / 'static/games/battle-chess/assets/skins' / THEME / filename
            asset.parent.mkdir(parents=True, exist_ok=True)
            download.value.save_as(str(asset))
            data = asset.read_bytes()
            magic, version, length = struct.unpack_from('<4sII', data)
            assert magic == b'glTF' and version == 2 and length == len(data)
            json_size = struct.unpack_from('<I', data, 12)[0]
            gltf = json.loads(data[20:20 + json_size])
            assert len(gltf['meshes']) >= 12
            assert len(gltf['materials']) >= 10
            # A theme switch during an asynchronous export must not change the file's collection.
            assert page.evaluate('''async () => {
                const theme = app.board.fantasy.theme;
                const pending = app.board.fantasy.exportAssets();
                await app.boardAppearance.setStyle(theme === 'elven' ? 'fantasy' : 'elven');
                const buffer = await pending;
                const length = new DataView(buffer).getUint32(12, true);
                const asset = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 20, length)));
                await app.boardAppearance.setStyle(theme === 'elven' ? 'elven' : 'fantasy');
                return asset.nodes.some(node => node.name === `${theme === 'elven' ? 'Sylvan Court' : 'Runeforge'} - original Battle Chess set`);
            }''')

            # Both scenes share one renderer and return to cached meshes without leaks.
            page.evaluate('window.originalRenderer = app.board.fantasy.renderer')
            for _ in range(2):
                page.get_by_role('button', name='Elven 3D', exact=True).click()
                page.get_by_role('button', name='Runeforge 3D', exact=True).click()
            if ELVEN:
                page.get_by_role('button', name='Elven 3D', exact=True).click()
            geometry_count = page.evaluate('app.board.fantasy.renderer.info.memory.geometries')
            for _ in range(2):
                page.get_by_role('button', name='Elven 3D', exact=True).click()
                page.get_by_role('button', name='Runeforge 3D', exact=True).click()
            if ELVEN:
                page.get_by_role('button', name='Elven 3D', exact=True).click()
            assert page.evaluate('app.board.fantasy.renderer === window.originalRenderer')
            assert page.evaluate('app.board.fantasy.renderer.info.memory.geometries') == geometry_count

            click_square('e2')
            page.get_by_role('button', name='Runeforge 3D' if ELVEN else 'Elven 3D', exact=True).click()
            assert page.evaluate('app.board.selectedSquare') == 'e2'
            assert page.evaluate('app.board.validMoves.some(move => move.to === "e4")')
            page.get_by_role('button', name='Elven 3D' if ELVEN else 'Runeforge 3D', exact=True).click()
            click_square('e2')

            page.set_viewport_size({'width': 390, 'height': 844})
            page.wait_for_timeout(200)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            move('e2', 'e4')
            # Native touch input rotates, while a subsequent tap still selects/moves.
            touch = browser.new_page(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
            touch.on('pageerror', lambda e: errors.append(str(e)))
            touch.goto(url)
            touch.wait_for_function('window.app?.setupWizard && app.board.fantasyActive')
            touch.evaluate('app.setupWizard.hide(); app.gameManager.startGame({selectedMinigames: []})')
            if ELVEN:
                touch.get_by_role('button', name='Elven 3D', exact=True).tap()
            cdp = touch.context.new_cdp_session(touch)
            rect = touch.locator('#fantasy-canvas').bounding_box()
            tx, ty = rect['x'] + rect['width'] / 2, rect['y'] + rect['height'] / 2
            before = touch.evaluate('app.gameManager.chess.fen()')
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': tx, 'y': ty}]})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': tx + 65, 'y': ty - 35}]})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            assert touch.evaluate('app.board.fantasy.yaw') < 0
            assert touch.evaluate('app.gameManager.chess.fen()') == before
            assert touch.evaluate('app.inputHandler.selectedSquare') is None
            touch.get_by_role('button', name='Reset', exact=True).tap()
            for square in ('e2', 'e4'):
                point = touch.evaluate('(sq) => app.board.fantasy.squareToScreen(sq)', square)
                rect = touch.locator('#fantasy-canvas').bounding_box()
                touch.touchscreen.tap(rect['x'] + point['x'], rect['y'] + point['y'])
                if square == 'e2':
                    touch.wait_for_function('app.inputHandler.selectedSquare === "e2"')
            assert touch.evaluate('app.gameManager.chess.get("e4").type') == 'p'
            touch.close()
            page.screenshot(path=str(output / 'mobile.png'), full_page=True)
            page.reload()
            page.wait_for_function('window.app?.setupWizard && window.app.board.fantasyActive')
            assert page.evaluate('app.board.fantasy.theme') == THEME

            # Failure on browsers without WebGL must leave chess playable.
            fallback = browser.new_page()
            fallback.add_init_script('''
                const original = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(type, ...args) {
                    return type.includes('webgl') ? null : original.call(this, type, ...args);
                };
            ''')
            fallback.goto(url)
            fallback.wait_for_function('window.app?.setupWizard')
            expect(fallback.locator('#game-canvas')).to_be_visible()
            expect(fallback.locator('#board-view-status')).to_contain_text('3D is unavailable')
            fallback.evaluate('app.setupWizard.hide(); app.gameManager.startGame({selectedMinigames: []})')
            assert fallback.evaluate('app.gameManager.attemptMove("e2", "e4").to') == 'e4'

            # Context loss must also return to Classic without losing the game.
            page.evaluate('app.setupWizard.hide(); app.gameManager.startGame({selectedMinigames: []})')
            page.evaluate('app.board.fantasy.renderer.getContext().getExtension("WEBGL_lose_context").loseContext()')
            expect(page.locator('#game-canvas')).to_be_visible()
            assert page.evaluate('app.gameManager.chess.get("e2").type') == 'p'
            expect(page.get_by_role('button', name='Elven 3D', exact=True)).to_be_disabled()
            assert not errors, errors
            print(f'PASS ({THEME}): 3D moves, capture, flip, top view, Classic, castling, en passant, promotion, check, mobile, theme persistence, cached switching, fallback, GLB ({len(data):,} bytes).')
            print(f'Previews: {output}')
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    run()
