import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { drawPlayerEmblem, playerEmblemMarkup } from '../static/games/battle-chess/js/PlayerEmblems.js';

const names = ['BaseMinigame', 'DodgingBattle', 'MashingBattle', 'TimingBattle', 'HighestCard', 'MemoryMatch'];

function harness() {
    let now = 0;
    let nextTimer = 1;
    const timers = new Map();
    function schedule(callback, delay, repeat = false) {
        const id = nextTimer++;
        timers.set(id, { callback, delay, due: now + delay, repeat });
        return id;
    }
    function tick(duration) {
        const until = now + duration;
        let callbacks = 0;
        while (true) {
            const next = [...timers.entries()].filter(([, timer]) => timer.due <= until)
                .sort((a, b) => a[1].due - b[1].due || a[0] - b[0])[0];
            if (!next) break;
            assert.ok(++callbacks < 100000, 'Timer callbacks must settle');
            const [id, timer] = next;
            now = timer.due;
            if (!timer.repeat) timers.delete(id);
            timer.callback(now);
            if (timer.repeat && timers.get(id) === timer) timer.due += timer.delay;
        }
        now = until;
    }
    class Element {
        children = [];
        style = {};
        dataset = {};
        listeners = new Map();
        classList = { add() {}, remove() {} };
        constructor(tag) { this.tag = tag; }
        appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
        insertBefore(child, sibling) {
            const index = this.children.indexOf(sibling);
            this.children.splice(index < 0 ? this.children.length : index, 0, child);
            child.parentNode = this;
        }
        addEventListener(name, handler) {
            if (!this.listeners.has(name)) this.listeners.set(name, new Set());
            this.listeners.get(name).add(handler);
        }
        removeEventListener(name, handler) { this.listeners.get(name)?.delete(handler); }
        remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(child => child !== this); }
        closest(selector) { return selector === '.hc-card' && this.className?.includes('hc-card') ? this : null; }
        querySelector() { return null; }
        getContext() { return new Proxy({}, { get: (object, key) => object[key] ?? (() => {}), set: (object, key, value) => { object[key] = value; return true; } }); }
    }
    const document = new Element('document');
    document.createElement = tag => new Element(tag);
    const math = Object.create(Math);
    math.random = () => 0.5;
    const context = vm.createContext({
        document, Math: math, performance: { now: () => now },
        drawPlayerEmblem, playerEmblemMarkup,
        setTimeout: (callback, delay) => schedule(callback, delay),
        setInterval: (callback, delay) => schedule(callback, delay, true),
        clearTimeout: id => timers.delete(id), clearInterval: id => timers.delete(id),
        requestAnimationFrame: callback => schedule(callback, 16),
        cancelAnimationFrame: id => timers.delete(id),
    });
    for (const name of names) {
        const source = readFileSync(new URL(`../static/games/battle-chess/js/minigames/${name}.js`, import.meta.url), 'utf8')
            .replace(/^import .*;\r?\n/gm, '').replace('export class ', 'class ');
        vm.runInContext(`${source}\nglobalThis.${name} = ${name};`, context, { filename: `${name}.js` });
    }
    const results = [];
    function game(name, aiIndex = 1, difficulty = 'medium', attackerColor = 'w') {
        const instance = new context[name]();
        instance.init(new Element('div'), {
            players: [{ name: 'White', isAI: aiIndex === 0 }, { name: 'Black', isAI: aiIndex === 1 }],
            aiDifficulty: difficulty, attackerColor, advantage: 'none', onEnd: result => results.push(result),
        });
        return instance;
    }
    return { context, tick, timers, results, game };
}

function click(game, index) { game._onClick({ target: game._cardEls[index] }); }

test('ending and destroying stop every managed timer and animation, and end only fires once', () => {
    const h = harness();
    const game = h.game('BaseMinigame');
    let callbacks = 0;
    game.setTimer(() => callbacks++, 100);
    game.setRepeatingTimer(() => callbacks++, 50);
    game.requestFrame(() => callbacks++);
    game.end({ attackerWins: true, tie: false });
    game.end({ attackerWins: false, tie: false });
    assert.equal(h.results.length, 1);
    assert.equal(h.timers.size, 0);
    h.tick(1000);
    assert.equal(callbacks, 0);

    const next = h.game('BaseMinigame');
    next.setTimer(() => callbacks++, 100);
    next.destroy();
    assert.equal(h.timers.size, 0);
    h.tick(1000);
    assert.equal(callbacks, 0);
});

test('mashing bots play either color with increasing real press rates, blocking human AI keys', () => {
    for (const ai of [0, 1]) {
        const presses = [];
        for (const difficulty of ['easy', 'medium', 'hard']) {
            const h = harness();
            const game = h.game('MashingBattle', ai, difficulty);
            game.start();
            h.tick(3500);
            assert.equal(game.running, true);
            game._onKeyDown({ key: ai === 0 ? 'a' : 'l' });
            assert.equal(game.p1Presses + game.p2Presses, 0);
            game._onKeyDown({ key: ai === 0 ? 'l' : 'a', repeat: true });
            assert.equal(game.p1Presses + game.p2Presses, 0);
            let count = 0;
            const press = game._press.bind(game);
            game._press = index => { if (index === ai) count++; press(index); };
            h.tick(3000);
            assert.ok(count > 0);
            assert.ok(ai === 0 ? game.position > 4 : game.position < 4);
            presses.push(count);
            game.destroy();
            assert.equal(h.timers.size, 0);
            h.tick(1000);
        }
        assert.ok(presses[0] < presses[1] && presses[1] < presses[2]);
    }
});

test('mashing reaches a real timed result and clears bot work', () => {
    const h = harness();
    const game = h.game('MashingBattle', 1);
    game.start();
    h.tick(25000);
    assert.equal(h.results.length, 1);
    assert.equal(h.results[0].attackerWins, false);
    assert.equal(h.results[0].tie, false);
    assert.equal(h.timers.size, 0);
});

test('timing bots react after the cue for either color, with difficulty affecting actual reaction', () => {
    for (const ai of [0, 1]) {
        const reactions = [];
        for (const difficulty of ['easy', 'medium', 'hard']) {
            const h = harness();
            const game = h.game('TimingBattle', ai, difficulty);
            game.start();
            game._onKeyDown({ key: ai === 0 ? 'a' : 'l' });
            assert.equal(ai === 0 ? game.p1Early : game.p2Early, false);
            h.tick(4000);
            assert.equal(game.phase, 'ready');
            h.tick(100);
            game._onKeyDown({ key: ai === 0 ? 'l' : 'a' });
            h.tick(1300);
            const reaction = ai === 0 ? game.p1Time : game.p2Time;
            assert.ok(reaction >= game.aiSettings.reaction[0]);
            assert.ok(reaction <= game.aiSettings.reaction[1]);
            reactions.push(reaction);
            assert.equal(game.position, ai === 0 ? 3 : 5);
            game.destroy();
            assert.equal(h.timers.size, 0);
        }
        assert.ok(reactions[0] > reactions[1] && reactions[1] > reactions[2]);
    }
});

test('dodging bots move through ordinary arena rules and ignore keys for the AI seat', () => {
    for (const ai of [0, 1]) {
        const h = harness();
        const game = h.game('DodgingBattle', ai, 'hard');
        const bot = ai === 0 ? game.p1 : game.p2;
        const human = ai === 0 ? game.p2 : game.p1;
        const originalBotX = bot.x;
        const originalHumanX = human.x;
        game._onKeyDown({ key: ai === 0 ? 'd' : 'l' });
        assert.equal(Object.keys(game.keys).length, 0);
        game._onKeyDown({ key: ai === 0 ? 'j' : 'a' });
        game._update(0.05);
        assert.notEqual(bot.x, originalBotX);
        assert.ok(human.x < originalHumanX);
        game.projectiles = [{ x: bot.x - 45, y: bot.y, vx: 120, vy: 0 }];
        const direction = game._chooseAIDirection(bot);
        assert.ok(direction.dy !== 0 || direction.dx > 0, 'Avoid an approaching projectile');
        assert.ok(Math.hypot(direction.dx, direction.dy) <= 1.00001);
        game.start();
        game.destroy();
        assert.equal(h.timers.size, 0);
    }
});

test('simultaneous dodging hits honor an extra life and immediately resolve the surviving player', () => {
    const h = harness();
    const game = h.game('DodgingBattle');
    game.p1.lives = 2;
    game.p1.x = game.p2.x;
    game.projectiles = [{ x: game.p1.x, y: game.p1.y, vx: 0, vy: 0 }];
    game._update(0);
    assert.equal(h.results.length, 1);
    assert.equal(h.results[0].attackerWins, true);
    assert.equal(h.results[0].tie, false);
});

test('highest card automatically takes the computer turn in both roles without reading card ranks', () => {
    for (const ai of [0, 1]) {
        for (const attacker of ['w', 'b']) {
            const h = harness();
            const game = h.game('HighestCard', ai, 'medium', attacker);
            game.deck = game.deck.map(card => new Proxy(card, {
                get(target, key) {
                    if (key === 'rank' && game.phase !== 'revealed') assert.fail('Bot inspected a face-down rank');
                    return target[key];
                },
            }));
            game.start();
            if (game.currentPicker !== ai) click(game, 0);
            const before = [game.p1Choice, game.p2Choice];
            click(game, 1);
            assert.deepEqual([game.p1Choice, game.p2Choice], before, 'Human cannot select an AI card');
            h.tick(800);
            assert.notEqual(ai === 0 ? game.p1Choice : game.p2Choice, null);
            if (game.phase === 'p2-pick') click(game, 0);
            assert.equal(game.phase, 'reveal-ready');
            assert.notEqual(game.p1Choice, game.p2Choice);
            game._reveal();
            h.tick(4000);
            assert.equal(h.results.length, 1);
            assert.equal(h.timers.size, 0);
        }
    }
});

test('memory bots learn public flips, never inspect hidden values, and block clicks on their turn', () => {
    for (const ai of [0, 1]) {
        const h = harness();
        const humanColor = ai === 0 ? 'b' : 'w';
        const game = h.game('MemoryMatch', ai, 'hard', humanColor);
        game.deck = game.deck.map((card, index) => new Proxy(card, {
            get(target, key) {
                if (key === 'value' && game.cardState[index] === 'down') assert.fail('Bot inspected a face-down value');
                return target[key];
            },
        }));
        game.start();
        assert.equal(game._aiMemory[ai].size, 0);
        game._rememberCard(4);
        assert.equal(game._aiMemory[ai].size, 0);
        click(game, 0);
        assert.equal(game._aiMemory[ai].get(0), game.deck[0].value);
        assert.equal(game.cardState[game._chooseAICard(ai)], 'down');
        game._flipBackTurn();
        game._switchTurn();
        click(game, 1);
        assert.equal(game.flippedThisTurn.length, 0);
        h.tick(400);
        assert.equal(game.flippedThisTurn.length, 1);
        game.destroy();
        assert.equal(h.timers.size, 0);
        h.tick(5000);
        assert.equal(h.results.length, 0);
    }
});

test('memory difficulty limits recall and a remembered set produces an ordinary matching win', () => {
    for (const [difficulty, limit] of [['easy', 16], ['medium', 32], ['hard', 52]]) {
        const h = harness();
        const game = h.game('MemoryMatch', 1, difficulty);
        for (let index = 0; index < 52; index++) {
            game.cardState[index] = 'up';
            game._rememberCard(index);
            game.cardState[index] = 'down';
        }
        assert.equal(game._aiMemory[1].size, limit);
    }
    for (const ai of [0, 1]) {
        const h = harness();
        const game = h.game('MemoryMatch', ai, 'hard', ai === 0 ? 'w' : 'b');
        const matches = [0, 1, 2, 3];
        for (const index of matches) {
            game.deck[index].value = 'A';
            game.cardState[index] = 'up';
            game._rememberCard(index);
            game.cardState[index] = 'down';
        }
        game.start();
        h.tick(6000);
        assert.equal(h.results.length, 1);
        assert.equal(h.results[0].attackerWins, true);
        assert.ok(matches.every(index => game.cardState[index] === 'matched'));
        assert.equal(h.timers.size, 0);
    }
});

test('local two-player games schedule no computer actions', () => {
    const h = harness();
    const mash = h.game('MashingBattle', -1);
    mash.start();
    h.tick(6500);
    assert.equal(mash.position, 4);
    assert.equal(mash.p1Presses + mash.p2Presses, 0);
    mash.destroy();
    const cards = h.game('HighestCard', -1);
    cards.start();
    h.tick(1000);
    assert.equal(cards.p1Choice, null);
    assert.equal(cards.p2Choice, null);
    cards.destroy();
});
