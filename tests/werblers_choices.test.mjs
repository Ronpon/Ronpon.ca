import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const choicesSource = readFileSync(new URL('../static/games/werblers/js/choices.js', import.meta.url), 'utf8');

function harness() {
  class Element {
    children = [];
    style = {};
    listeners = {};
    classList = {add() {}, remove() {}};
    constructor(tag) { this.tag = tag; }
    setAttribute() {}
    append(...children) { children.forEach(child => this.appendChild(child)); }
    appendChild(child) { this.children.push(child); child.parent = this; }
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
    addEventListener(name, listener) { this.listeners[name] = listener; }
    focus() { document.activeElement = this; }
    querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
  }
  const document = {
    body: new Element('body'), activeElement: null,
    createElement: tag => new Element(tag), getElementById: () => new Element('div'),
  };
  const requests = [];
  const fights = [];
  const state = {
    current_player_id: 0,
    players: [{player_id: 0, name: 'Source', curses: []},
      {player_id: 1, name: 'Responder', curses: [{name: 'First'}, {name: 'Second'}]}],
    pending_me_too: {id: 7, player_id: 1, source_player_id: 0},
  };
  const sandbox = {
    window: {}, document,
    fetch: async (url, init) => {
      requests.push({url, data: JSON.parse(init.body)});
      return {ok: true, json: async () => ({state: {...state, pending_me_too: null}})};
    },
    applyState: next => sandbox.window.werblersChoices.render(next),
    playMusic() {}, showPreFightScene: (...args) => fights.push(args),
    _showCharlieWorkDecision: level => fights.push(['charlie_work', level]),
  };
  vm.createContext(sandbox);
  vm.runInContext(choicesSource, sandbox);
  return {sandbox, state, requests, fights, document};
}

test('Me Too waits for an explicit choice and submits the selected curse only once', async () => {
  const h = harness();
  h.sandbox.window.werblersChoices.render(h.state);
  assert.equal(h.requests.length, 0);
  const buttons = h.document.body.querySelectorAll('button');
  assert.equal(buttons.length, 3);
  const firstClick = buttons[1].listeners.click();
  await buttons[1].listeners.click();
  await firstClick;
  assert.equal(h.requests.length, 1);
  assert.deepEqual(h.requests[0].data, {choice_id: 7, curse_index: 1});
  assert.equal(h.document.body.children.length, 0);
});

test('Me Too can be declined without selecting a curse', async () => {
  const h = harness();
  h.sandbox.window.werblersChoices.render(h.state);
  await h.document.body.querySelectorAll('button')[2].listeners.click();
  assert.equal(h.requests[0].data.curse_index, null);
});

test('A failed Me Too request keeps the choice available for retry', async () => {
  const h = harness();
  h.sandbox.fetch = async () => { throw new Error('Connection lost'); };
  h.sandbox.window.werblersChoices.render(h.state);
  const buttons = h.document.body.querySelectorAll('button');
  await buttons[0].listeners.click();
  assert.ok(buttons.every(button => !button.disabled));
  assert.equal(h.document.body.children.length, 1);
});

for (const path of ['werblers/js/game.js', 'werblers-mobile/js/ios_game.js']) {
  for (const name of ['_doLoad', 'menuLoadGame']) {
    test(`${path}: ${name} reopens the saved combat`, async () => {
      const h = harness();
      const source = readFileSync(new URL('../static/games/' + path, import.meta.url), 'utf8');
      const start = source.indexOf(`async function ${name}()`);
      const end = source.indexOf('\n}', start) + 2;
      const combat = {monster_name: 'Saved monster'};
      Object.assign(h.sandbox, {
        _selectedSlot: 1, _profileId: 1, _profileToken: 'test', _boardBuilt: true,
        viewingPlayerId: 0, gameState: null,
        closeSaveLoadModal() {}, closeMenuLoadModal() {}, buildBoard() {},
        _resumeTierMusic() {}, loadAndRenderAbilities: async () => {},
        fetch: async () => ({json: async () => ({ok: true, state: h.state,
          resume: {phase: 'combat', combat_info: combat}})}),
      });
      vm.runInContext(source.slice(start, end), h.sandbox);
      await h.sandbox[name]();
      assert.equal(h.fights.length, 1);
      assert.equal(h.fights[0][0], combat);
      assert.equal(h.fights[0][1], h.state);
    });
  }
}

test('Loading an unresolved Charlie Work choice restores its tier', () => {
  const h = harness();
  h.sandbox.window.werblersChoices.resumeLoadedCombat({resume: {phase: 'charlie_work', level: 2}});
  assert.deepEqual(h.fights, [['charlie_work', 2]]);
});

test('Slurp requires two explicit trait choices and sends the selected indices once', async () => {
  const h = harness();
  h.state.pending_me_too = null;
  h.state.pending_trait_loss = {id: 9, player_id: 0, count: 2};
  h.state.players[0].traits = [{name:'Keep'}, {name:'Lose A'}, {name:'Lose B'}];
  h.sandbox.fetch = async (url, init) => {
    h.requests.push({url, data: JSON.parse(init.body)});
    return {ok:true, json:async () => ({state:{...h.state,pending_trait_loss:null}})};
  };
  h.sandbox.window.werblersChoices.render(h.state);
  const inputs = h.document.body.querySelectorAll('input');
  const confirm = h.document.body.querySelectorAll('button')[0];
  assert.equal(confirm.disabled, true);
  for (const input of inputs.slice(1)) {
    input.checked = true;
    input.listeners.change();
  }
  assert.equal(confirm.disabled, false);
  const submitted = confirm.listeners.click();
  await confirm.listeners.click();
  await submitted;
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, '/games/werblers/api/resolve_trait_loss');
  assert.deepEqual(h.requests[0].data, {choice_id:9, trait_indices:[1,2]});
  assert.equal(h.document.body.children.length, 0);
});

for (const phase of ['chest','shop','mystery','rake_it_in']) {
  test(`Loading ${phase} restores the appropriate interaction and data`, () => {
    const h = harness();
    h.state.pending_me_too = null;
    Object.assign(h.state.players[0], {helmets:[],chest_armor:[],leg_armor:[],weapons:[],pack:[],consumables:[]});
    const shown = [];
    Object.assign(h.sandbox, {
      _pendingOfferData:null, _pendingOfferType:null,
      showChestModal: (...args) => shown.push(['chest', ...args]),
      showShopModal: (...args) => shown.push(['shop', ...args]),
      showMysteryEventModal: (...args) => shown.push(['mystery', ...args]),
      showRakeItInModal: (...args) => shown.push(['rake_it_in', ...args]),
    });
    const d = {phase,player_id:0,items:[{name:'Saved reward'}],scavenger:true,sub_type:'shop',
      event:{event_id:'the_wheel',name:'The Wheel',tier:2}};
    h.sandbox.window.werblersChoices.resumeGame({state:h.state,resume:d});
    assert.equal(shown.length,1);
    assert.equal(shown[0][0],phase);
    if (phase === 'chest' || phase === 'shop') {
      assert.equal(h.sandbox._pendingOfferData.items,d.items);
      assert.equal(h.sandbox._pendingOfferData.has_scavenger,true);
    } else if (phase === 'mystery') {
      assert.equal(shown[0][1].image,'Events/The Wheel Tier 2.png');
    } else assert.equal(shown[0][1].shop_remaining,d.items);
  });
}

test('Loading an out-of-turn minion keeps the owner and proceeds to their next reward', async () => {
  const h = harness();
  h.state.pending_me_too = null;
  h.state.players[1].minions = [];
  h.state.players[1].max_minions = 2;
  h.sandbox.window.werblersChoices.resumeGame({state:h.state,
    resume:{phase:'minion',player_id:1,minion:{name:'Friend'}}});
  await h.document.body.querySelectorAll('button')[0].listeners.click();
  assert.deepEqual(h.requests[0].data,{player_id:1,replace_index:-1});
});
