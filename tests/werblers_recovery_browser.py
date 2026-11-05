"""Real desktop/mobile recovery flows and layout checks, using temporary saves."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server, WSGIRequestHandler
from test_site_theme import isolated_app
from test_werblers_review import johnil_game, land
from werblers_engine import content as C, database as game_db
from werblers_engine.game import Game
from werblers_engine.heroes import HeroId
from werblers_engine.mystery import MysteryEvent
from werblers_engine.save_load import serialize_game
from werblers_engine.types import EquipSlot, Item, Minion, TileType, Trait
from werblers_web.routes import helpers


class Quiet(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def run():
    with tempfile.TemporaryDirectory(prefix='werblers-recovery-') as directory:
        app, _ = isolated_app(directory)
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=Quiet)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = pw.chromium.launch(headless=True, **({'executable_path':str(edge)} if edge.exists() else {}))
                for mobile in (False, True):
                    mode = 'mobile' if mobile else 'desktop'
                    size = {'width':390,'height':844} if mobile else {'width':1360,'height':900}
                    context = browser.new_context(viewport=size, is_mobile=mobile, has_touch=mobile)
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
                    with page.expect_response(lambda r: '/api/profiles?' in r.url):
                        page.goto(origin + ('/games/werblers-mobile' if mobile else '/games/werblers'), wait_until='domcontentloaded')
                    page.locator('#profile-name-input').fill('Recovery review')
                    page.get_by_role('button', name='Create', exact=True).click()
                    page.get_by_role('button', name='New Game', exact=True).click()
                    if mobile:
                        page.get_by_role('button', name='1', exact=True).click()
                        page.get_by_role('button', name='Continue', exact=True).click()
                    page.evaluate("async () => { numPlayers=1; heroSelections={0:'RIZZT'}; await startGame(); }")
                    expect(page.locator('#game-screen')).to_be_visible()
                    page.evaluate("async () => { await Promise.all([...document.querySelectorAll('#game-screen img')].map(i=>i.decode().catch(()=>{}))); }")
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), mode + ': horizontal overflow'
                    if mobile:
                        expect(page.locator('.tile-number')).to_have_count(90)
                        expect(page.locator('.is-current-position')).to_have_count(1)
                        assert 'Tile 1' in page.locator('#turn-banner').inner_text()
                        assert not any(c in page.locator('#turn-banner').inner_text() for c in ('\u00c3','\u00c2'))
                        first = page.locator('.tile[data-index="1"]').bounding_box()
                        second_row = page.locator('.tile[data-index="11"]').bounding_box()
                        assert abs(first['y'] - second_row['y']) <= first['height'] + 3, 'Large gaps between board rows'
                        assert 'user-scalable=no' not in page.locator('meta[name=viewport]').get_attribute('content')
                    else:
                        toolbar = page.locator('#werblers-toolbar').bounding_box()
                        legend = page.locator('#board-legend').bounding_box()
                        assert toolbar['y'] + toolbar['height'] <= legend['y'], 'Navigation covers board legend'
                        assert page.locator('#movement-section').bounding_box()['y'] < 600, 'Movement controls too far below player stats'
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / f'werblers-fixed-{mode}.png'), full_page=True)

                    def saved_game(game):
                        game_db.save_game(page.evaluate('_profileId'), 1, serialize_game(game),
                                          game.turn_number, len(game.players), ', '.join(p.name for p in game.players))
                        page.evaluate('async () => { _selectedSlot=1; await menuLoadGame(); }')

                    def current_game():
                        cookie = next(c['value'] for c in context.cookies() if c['name'] == app.config['SESSION_COOKIE_NAME'])
                        session = app.session_interface.get_signing_serializer(app).loads(cookie)
                        return helpers._sessions[session['game_id']]['game']

                    game = Game(hero_ids=[HeroId.RIZZT], seed=1)
                    land(game, TileType.CHEST)
                    saved_game(game)
                    expect(page.locator('#offer-modal')).to_be_visible()
                    page.get_by_role('button', name='Leave It', exact=True).click()
                    expect(page.locator('#offer-modal')).to_be_hidden()

                    game = Game(hero_ids=[HeroId.RIZZT], seed=1)
                    game.player.traits.append(Trait('Scavenger', effect_id='scavenger'))
                    land(game, TileType.SHOP)
                    old = [i.name for i in game._pending_offer['items']]
                    saved_game(game)
                    swap = page.get_by_role('button', name='Scavenger: Replace selected item', exact=True)
                    expect(swap).to_be_disabled()
                    page.locator('#offer-modal .offer-item-name').nth(1).click()
                    expect(swap).to_be_enabled()
                    with page.expect_response('**/api/scavenger_swap'):
                        swap.click()
                    expect(swap).to_have_count(0)
                    assert page.evaluate('_pendingOfferData.items[0].name') == old[0]
                    assert page.evaluate('_pendingOfferData.items[1].name') != old[1]
                    page.get_by_role('button', name='Leave Shop', exact=True).click()

                    saved_game(johnil_game())
                    page.evaluate('doFight()')
                    loss = page.get_by_role('dialog', name='Choose traits to lose', exact=True)
                    expect(loss).to_be_visible()
                    # Reload the already-resolved fight while its loss choice is pending.
                    saved_game(current_game())
                    expect(loss).to_be_visible()
                    confirm = loss.get_by_role('button', name='Discard 2 selected traits', exact=True)
                    loss.get_by_role('checkbox', name='Lose A', exact=True).check()
                    expect(confirm).to_be_disabled()
                    loss.get_by_role('checkbox', name='Lose B', exact=True).check()
                    confirm.click()
                    expect(loss).to_have_count(0)
                    assert [t.name for t in current_game().players[0].traits] == ['Keep']
                    assert current_game().current_player.player_id == 1

                    game = Game(num_players=2, seed=1)
                    game._current_player_idx = 1
                    game.players[0].pending_trait_items = [Item('Reward A',EquipSlot.HELMET), Item('Reward B',EquipSlot.HELMET)]
                    game.players[0].pending_trait_minions = [Minion('Friend',strength_bonus=2)]
                    saved_game(game)
                    reward = page.get_by_role('dialog', name='Finish your reward choice', exact=True)
                    for name in ('Reward A', 'Reward B'):
                        expect(reward).to_contain_text(name)
                        reward.get_by_role('button', name='Keep in pack', exact=True).click()
                    expect(reward).to_contain_text('Friend')
                    reward.get_by_role('button', name='Add minion', exact=True).click()
                    expect(reward).to_have_count(0)
                    assert [i.name for i in current_game().players[0].pack] == ['Reward A','Reward B']
                    assert len(current_game().players[1].pack) == 0

                    game = Game(seed=1)
                    land(game, TileType.MYSTERY)
                    game._pending_offer['event'] = MysteryEvent('mystery_box','Mystery Box',1,'Choose a wager','Mystery Box')
                    saved_game(game)
                    expect(page.locator('#battle-overlay')).to_contain_text('Mystery Box')
                    expect(page.get_by_role('button', name='Decline', exact=True)).to_be_visible()

                    game = Game(seed=1)
                    land(game, TileType.CHEST)
                    game._pending_offer.update(type='fairy_king_reward', reward_items=[deepcopy(C.ITEM_POOL_L3[0])])
                    saved_game(game)
                    reward.get_by_role('button').click()
                    expect(page.locator('#offer-modal')).to_be_visible()
                    page.get_by_role('button', name='Leave It', exact=True).click()

                    game = Game(seed=1)
                    land(game, TileType.CHEST)
                    game._pending_offer.update(type='rake_it_in',sub_type='chest',shop_remaining=[],log=[])
                    saved_game(game)
                    expect(page.locator('#rake-it-in-modal')).to_be_visible()
                    assert not errors, (mode, errors)
                    print(f'{mode}: layout, Scavenger, boss loss, all reward owners and pending-offer recovery OK')
                    context.close()
                browser.close()
        finally:
            server.shutdown()


if __name__ == '__main__':
    run()
