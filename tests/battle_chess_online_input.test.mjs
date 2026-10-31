import test from 'node:test';
import assert from 'node:assert/strict';
import { OnlineBattleScreen } from '../static/games/battle-chess/js/OnlineBattleScreen.js';

globalThis.document = { hidden: false, removeEventListener() {} };
globalThis.window = { removeEventListener() {} };
globalThis.cancelAnimationFrame = () => {};

function fixture(gameId = 'mashing-battle') {
    const requests = [];
    const online = { connected: true, busy: false, generation: 1, code: 'ABC234' };
    const screen = new OnlineBattleScreen(online);
    screen.id = 'battle';
    screen.room = { you: 'w', battle: { id: 'battle', gameId, phase: 'playing', outcome: null, ack: 0 } };
    online._request = (path, body) => new Promise((resolve, reject) => {
        requests.push({ body: { ...body }, resolve, reject });
    });
    online._accept = room => {
        screen.room = room;
        if (screen.pending && room.battle.ack >= screen.pending.seq) screen.pending = null;
        online.connected = true;
    };
    const finish = async index => {
        const request = requests[index];
        request.resolve({ room: { ...screen.room, battle: { ...screen.room.battle, ack: request.body.seq } } });
        await new Promise(resolve => setImmediate(resolve));
    };
    return { screen, online, requests, finish };
}

test('presses arriving during a request are sent next with a new sequence', async () => {
    const { screen, requests, finish } = fixture();
    screen._tap();
    for (let i = 0; i < 4; i++) screen._tap();
    assert.equal(requests.length, 1);
    assert.equal(requests[0].body.taps, 1);
    await finish(0);
    assert.equal(requests.length, 2);
    assert.equal(requests[1].body.taps, 4);
    assert.equal(requests[1].body.seq, 2);
    await finish(1);
    assert.equal(requests.length, 2);
});

test('a movement key release is flushed immediately after the held-key request', async () => {
    const { screen, requests, finish } = fixture('dodging-battle');
    const event = { key: 'd', target: { tagName: 'CANVAS' }, repeat: false, preventDefault() {} };
    screen._key(event, true);
    screen._key(event, false);
    assert.equal(requests[0].body.keys, 8);
    await finish(0);
    assert.equal(requests[1].body.keys, 0);
    await finish(1);
});

test('a lost response retries the identical sequence and clears held input afterward', async () => {
    const { screen, online, requests, finish } = fixture();
    screen._tap();
    requests[0].reject(new TypeError('network interrupted'));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(online.connected, false);
    screen.sendFrame();
    assert.deepEqual(requests[1].body, requests[0].body);
    await finish(1);
    assert.equal(requests[2].body.taps, 0);
    assert.equal(requests[2].body.seq, 2);
    await finish(2);
});

test('repeat keys and the other seat cannot submit a timing reaction', async () => {
    const { screen, requests, finish } = fixture('timing-battle');
    Object.assign(screen.room.battle, { stage: 'signal', round: 1, cue: 'cue', reactions: {} });
    const event = { key: 'a', target: { tagName: 'BUTTON' }, repeat: true, preventDefault() {} };
    screen._key(event, true);
    screen._key({ ...event, repeat: false, key: 'l' }, true);
    assert.equal(requests.length, 0);
    screen._key({ ...event, repeat: false }, true);
    screen._tap();
    assert.equal(requests.length, 1);
    assert.equal(requests[0].body.cue, 'cue');
    await finish(0);
});

test('teardown ignores a response from a previous battle screen', async () => {
    const { screen, online, requests } = fixture();
    let applied = false;
    online._accept = () => { applied = true; };
    screen._tap();
    screen.destroy();
    requests[0].resolve({ room: {} });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(applied, false);
    assert.equal(screen.sending, false);
});

test('Space keeps its normal button action on readiness and Leave controls', () => {
    const { screen, requests } = fixture();
    const event = { key: ' ', target: { tagName: 'BUTTON', id: 'battle-leave' }, repeat: false,
        preventDefault() { assert.fail('The normal button action must remain available'); } };
    screen._key(event, true);
    screen.room.battle.phase = 'ready';
    screen._key({ ...event, target: { tagName: 'BUTTON', id: 'battle-ready-action' } }, true);
    assert.equal(requests.length, 0);
});
