"""Two real browser contexts: desktop host + mobile guest, temporary databases."""
from pathlib import Path
from copy import deepcopy
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server, WSGIRequestHandler
from test_site_theme import isolated_app


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs): pass


def run():
    with tempfile.TemporaryDirectory(prefix='werblers-browser-') as directory:
        app, _ = isolated_app(directory)
        from werblers_web import rooms
        from werblers_engine.types import TileType, Trait, Curse
        from werblers_engine import content as C
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = pw.chromium.launch(headless=True, **({'executable_path':str(edge)} if edge.exists() else {}))
                desktop = browser.new_context(viewport={'width':1360,'height':1000})
                mobile = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
                host, guest = desktop.new_page(), mobile.new_page()
                errors=[]
                host.on('pageerror', lambda e: errors.append(str(e)))
                guest.on('pageerror', lambda e: errors.append(str(e)))
                host.goto(origin+'/games/werblers')
                host.get_by_role('button',name='Play Online',exact=True).filter(visible=True).click()
                host.locator('form[data-form=create] [name=name]').fill('Host <safe>')
                host.get_by_role('button',name='Create private room',exact=True).click()
                expect(host.locator('.wo-code')).to_be_visible()
                code=host.locator('.wo-code').inner_text()
                guest.goto(origin+'/games/werblers-mobile?room='+code)
                guest.locator('form[data-form=join] [name=name]').fill('Phone guest')
                guest.get_by_role('button',name='Join room',exact=True).click()
                expect(guest.locator('.wo-code')).to_have_text(code)
                host.get_by_role('button',name='Choose Gregory',exact=True).click()
                expect(guest.locator('#wo-seats')).to_contain_text('Gregory')
                guest.get_by_role('button',name='Choose Brunhilde the Bodacious',exact=True).click()
                expect(host.get_by_role('button',name='Start adventure',exact=True)).to_be_enabled()
                host.get_by_role('button',name='Start adventure',exact=True).click()
                expect(host.locator('form[data-form=begin_move]')).to_be_visible()
                expect(guest.locator('#wo-waiting')).to_contain_text('Host <safe>')
                expect(guest.locator('form[data-form=begin_move]')).to_have_count(0)
                assert not guest.locator('.wo-room-details').evaluate('(el)=>el.open')
                assert guest.locator('#wo-waiting').bounding_box()['y'] < 500, 'Turn status is below the first phone screen'

                def seed(callback):
                    with rooms.locked_room(code) as (_, room):
                        state=rooms.load_state(room);callback(state['game'],room)
                        rooms.store_state(room,state);room['version']+=1

                def chest(game,room):
                    game.player.position=11;game.player.movement_hand=[1,1,1,1]
                    game.board[12].tile_type=TileType.CHEST
                seed(chest)
                expect(host.locator('#wo-screen')).to_contain_text('Tile 11')
                host.get_by_role('button',name='Play movement card',exact=True).click()
                expect(host.locator('form[data-form=resolve_offer]')).to_be_visible()
                host.reload()
                host.get_by_role('button',name='Play Online',exact=True).filter(visible=True).click()
                host.get_by_role('button',name=code,exact=True).click()
                expect(host.locator('form[data-form=resolve_offer]')).to_be_visible()
                host.get_by_role('button',name='Take item',exact=True).click()
                expect(guest.locator('form[data-form=begin_move]')).to_be_visible()

                def me_too(game,room):
                    p=game.players[1]
                    p.traits.append(Trait('Eight Lives',effect_id='eight_lives'))
                    p.curses.append(Curse('Source curse'))
                    game.players[0].traits.append(Trait('Me Too!',effect_id='me_too'))
                    game.players[0].curses.append(Curse('Host curse'))
                seed(me_too)
                expect(guest.locator('form[data-form=begin_move] summary')).to_have_text('Abilities')
                guest.locator('form[data-form=begin_move] summary').click()
                guest.get_by_role('button',name='Eight Lives: remove Source curse',exact=True).click()
                expect(host.get_by_role('button',name='Discard Host curse',exact=True)).to_be_visible()
                host.get_by_role('button',name='Keep my curses',exact=True).click()
                expect(guest.locator('form[data-form=begin_move]')).to_be_visible()

                host.get_by_text('Host controls',exact=True).click()
                host.get_by_role('button',name='Pause room',exact=True).click()
                expect(guest.locator('#wo-waiting')).to_have_text('The host paused the room.')
                host.get_by_role('button',name='Skip turn / decision',exact=True).nth(1).click()
                host.get_by_role('button',name='Resume room',exact=True).click()
                expect(host.locator('form[data-form=begin_move]')).to_be_visible()

                host.get_by_role('button',name='Replace with AI',exact=True).nth(1).click()
                expect(host.get_by_role('button',name='Return to human',exact=True)).to_be_visible()
                host.get_by_role('button',name='Return to human',exact=True).click()
                expect(host.get_by_role('button',name='Replace with AI',exact=True)).to_have_count(2)
                expect(guest.locator('#wo-waiting')).to_contain_text('Host <safe>')
                def johnil(game, room):
                    game._current_player_idx = 0
                    player = game.players[0]
                    player.position = 89
                    player.movement_hand = [1]
                    player.miniboss1_defeated = player.miniboss2_defeated = True
                    player.traits = [Trait('Keep'),Trait('Lose A'),Trait('Lose B')]
                    game.player_werblers[0] = next(deepcopy(b) for b in C.WERBLER_POOL if b.effect_id == 'johnil')
                seed(johnil)
                expect(host.locator('#wo-screen')).to_contain_text('Tile 89')
                host.get_by_role('button',name='Play movement card',exact=True).click()
                host.get_by_role('button',name='Fight',exact=True).click()
                expect(host.locator('form[data-form=resolve_trait_loss]')).to_be_visible()
                expect(guest.locator('form[data-form=resolve_trait_loss]')).to_have_count(0)
                host.get_by_role('checkbox',name='Lose A',exact=True).check()
                expect(host.get_by_role('button',name='Discard selected traits',exact=True)).to_be_disabled()
                host.get_by_role('checkbox',name='Lose B',exact=True).check()
                host.get_by_role('button',name='Discard selected traits',exact=True).click()
                expect(guest.locator('form[data-form=begin_move]')).to_be_visible()
                host.locator('#wo-screen').evaluate('(el)=>el.scrollTop=0')
                guest.locator('#wo-screen').evaluate('(el)=>el.scrollTop=0')
                assert guest.locator('form[data-form=begin_move]').bounding_box()['y'] < 500, 'Turn controls require scrolling on a phone'
                host.screenshot(path=str(Path(tempfile.gettempdir())/'werblers-online-desktop.png'),full_page=True)
                guest.screenshot(path=str(Path(tempfile.gettempdir())/'werblers-online-mobile.png'),full_page=True)
                assert guest.locator('#wo-screen').evaluate('(el)=>el.scrollWidth <= el.clientWidth'), 'Mobile horizontal overflow'
                assert not errors, errors
                browser.close()
                print('Desktop/mobile private room, turns, reconnect, chest placement, Me Too, pause and skip: OK')
                print('Screenshots: '+str(Path(tempfile.gettempdir())/'werblers-online-desktop.png'))
        finally:
            server.shutdown()


if __name__=='__main__':run()
