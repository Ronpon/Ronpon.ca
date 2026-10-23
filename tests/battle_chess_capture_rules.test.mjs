import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { GameManager } from '../static/games/battle-chess/js/GameManager.js';
import { EventBus } from '../static/games/battle-chess/js/EventBus.js';
import { GameEvent, GameState } from '../static/games/battle-chess/js/Constants.js';

const require = createRequire(import.meta.url);
const { Chess } = require('../static/games/battle-chess/lib/chess.js');
globalThis.Chess = Chess;

function game(fen, attackerLosesPiece = true) {
    const bus = new EventBus();
    const manager = new GameManager(bus);
    manager.startGame({ playerCount: 2, attackerLosesPiece, selectedMinigames: ['highest-card'] });
    if (fen) assert.equal(manager.chess.load(fen), true);
    const endings = [];
    bus.on(GameEvent.GAME_OVER, result => endings.push(result));
    return { manager, bus, endings };
}

function lose(manager, from, to) {
    assert.equal(manager.attemptMove(from, to)?.pending, true, `${from}-${to} should start a battle`);
    manager.resolveCapture({ attackerWins: false });
    assert.equal(manager.pendingMove, null);
}

test('failed pawn captures remove either color only when enabled, leaving the defender', () => {
    for (const fixture of [
        { fen: '4k3/8/8/3p4/4P3/8/8/4K3 w - - 62 8', color: 'w', from: 'e4', to: 'd5' },
        { fen: '4k3/8/8/4p3/3P4/8/8/4K3 b - - 62 8', color: 'b', from: 'e5', to: 'd4' }
    ]) {
        for (const removal of [false, true]) {
            const { manager, endings } = game(fixture.fen, removal);
            const defender = manager.chess.get(fixture.to);
            lose(manager, fixture.from, fixture.to);
            assert.equal(manager.chess.get(fixture.from)?.color ?? null, removal ? null : fixture.color);
            assert.deepEqual(manager.chess.get(fixture.to), defender);
            assert.equal(manager.chess.turn(), fixture.color === 'w' ? 'b' : 'w');
            assert.equal(manager.state, GameState.PLAYING);
            assert.equal(endings.length, 0);
            assert.equal(manager.chess.fen().split(' ')[4], removal ? '0' : '63');
            assert.equal(manager.chess.fen().split(' ')[5], fixture.color === 'b' ? '9' : '8');
            manager.reset();
        }
    }
});

test('checked attackers keep their turn and can answer check after losing, for both colors', () => {
    for (const fixture of [
        { fen: '4k3/8/8/8/8/8/4r3/3QK3 w - - 99 8', from: 'd1', to: 'e2', king: 'e1', escape: 'd1' },
        { fen: '3qk3/4R3/8/8/8/8/8/4K3 b - - 99 8', from: 'd8', to: 'e7', king: 'e8', escape: 'd8' }
    ]) {
        for (const removal of [false, true]) {
            const { manager, endings } = game(fixture.fen, removal);
            const color = manager.chess.turn();
            lose(manager, fixture.from, fixture.to);
            assert.equal(manager.chess.get(fixture.from)?.color ?? null, removal ? null : color);
            assert.equal(manager.chess.turn(), color);
            assert.equal(manager.chess.in_check(), true);
            assert.equal(manager.state, GameState.PLAYING);
            assert.equal(endings.length, 0);
            assert.equal(manager.chess.fen().split(' ')[4], removal ? '0' : '99');
            assert.equal(manager.chess.fen().split(' ')[5], '8');
            // With removal disabled the queen still occupies this escape square.
            const escape = removal ? fixture.escape : (color === 'w' ? 'f1' : 'f8');
            assert.ok(manager.attemptMove(fixture.king, escape));
            assert.notEqual(manager.chess.turn(), color);
            manager.reset();
        }
    }
});

test('removing a pinned failed attacker exposes check without a synthetic loss', () => {
    for (const fixture of [
        { fen: '4rk2/8/8/8/8/8/4R3/4K3 w - - 0 1', from: 'e2', to: 'e8', king: 'e1', escape: 'd1' },
        { fen: '4k3/4r3/8/8/8/8/8/4RK2 b - - 0 1', from: 'e7', to: 'e1', king: 'e8', escape: 'd8' }
    ]) {
        const { manager, endings } = game(fixture.fen);
        const color = manager.chess.turn();
        assert.equal(manager.chess.in_check(), false);
        lose(manager, fixture.from, fixture.to);
        assert.equal(manager.chess.get(fixture.from), null);
        assert.equal(manager.chess.in_check(), true);
        assert.equal(manager.chess.turn(), color);
        assert.equal(manager.state, GameState.PLAYING);
        assert.equal(endings.length, 0);
        assert.ok(manager.attemptMove(fixture.king, fixture.escape));
        manager.reset();
    }
});

test('a pinned removal exposing both kings allows check replies without king capture or forfeiture', () => {
    for (const fixture of [
        { fen: '4r3/8/8/8/6k1/8/4R3/3BK3 w - - 0 1', from: 'e2', to: 'e8',
            bishop: 'd1', otherKing: 'g4', king: 'e1', escape: 'd2', otherEscape: 'g5' },
        { fen: '3bk3/4r3/8/6K1/8/8/8/4R3 b - - 0 1', from: 'e7', to: 'e1',
            bishop: 'd8', otherKing: 'g5', king: 'e8', escape: 'd7', otherEscape: 'g4' }
    ]) {
        const { manager, endings } = game(fixture.fen);
        const color = manager.chess.turn();
        lose(manager, fixture.from, fixture.to);
        assert.equal(manager.chess.get(fixture.from), null);
        assert.equal(manager.chess.turn(), color);
        assert.equal(manager.chess.in_check(), true);
        assert.equal(manager.state, GameState.PLAYING);
        assert.equal(endings.length, 0);
        const opposite = manager.chess.fen().split(' ');
        opposite[1] = color === 'w' ? 'b' : 'w';
        assert.equal(new Chess(opposite.join(' ')).in_check(), true);
        // The active checked side must resolve its check rather than take the
        // other king along the newly opened bishop diagonal.
        assert.equal(manager.attemptMove(fixture.bishop, fixture.otherKing), null);
        assert.ok(manager.chess.moves({ verbose: true }).every(move => move.captured !== 'k'));
        assert.ok(manager.attemptMove(fixture.king, fixture.escape));
        assert.notEqual(manager.chess.turn(), color);
        assert.equal(manager.chess.in_check(), true);
        assert.ok(manager.attemptMove(fixture.otherKing, fixture.otherEscape));
        assert.equal(manager.chess.in_check(), false);
        assert.equal(manager.chess.board().flat().filter(piece => piece?.type === 'k').length, 2);
        assert.equal(manager.state, GameState.PLAYING);
        assert.equal(endings.length, 0);
        manager.reset();
    }
});

test('failed king captures preserve both pieces and continue, including while checked', () => {
    for (const fixture of [
        { fen: '7k/8/8/8/8/8/1p6/1K6 w - - 0 1', from: 'b1', to: 'b2', checked: false },
        { fen: '1k6/1P6/8/8/8/8/8/7K b - - 0 1', from: 'b8', to: 'b7', checked: false },
        { fen: '7k/8/8/8/8/8/4r3/4K3 w - - 0 1', from: 'e1', to: 'e2', checked: true },
        { fen: '4k3/4R3/8/8/8/8/8/7K b - - 0 1', from: 'e8', to: 'e7', checked: true }
    ]) {
        const { manager, endings } = game(fixture.fen);
        const color = manager.chess.turn();
        const defender = manager.chess.get(fixture.to);
        lose(manager, fixture.from, fixture.to);
        assert.deepEqual(manager.chess.get(fixture.from), { type: 'k', color });
        assert.deepEqual(manager.chess.get(fixture.to), defender);
        assert.equal(manager.chess.turn(), fixture.checked ? color : (color === 'w' ? 'b' : 'w'));
        assert.equal(manager.chess.in_check(), fixture.checked);
        assert.equal(manager.state, GameState.PLAYING);
        assert.equal(endings.length, 0);
        assert.ok(manager.chess.moves().length);
        manager.reset();
    }
});

test('lost corner rooks revoke only their own castling right', () => {
    for (const [color, from, to, rights] of [
        ['w', 'h1', 'h8', 'Qkq'], ['w', 'a1', 'a8', 'Kkq'],
        ['b', 'h8', 'h1', 'KQq'], ['b', 'a8', 'a1', 'KQk']
    ]) {
        const { manager } = game(`r3k2r/8/8/8/8/8/8/R3K2R ${color} KQkq - 0 1`);
        lose(manager, from, to);
        assert.equal(manager.chess.get(from), null);
        assert.equal(manager.chess.get(to).type, 'r');
        assert.equal(manager.chess.fen().split(' ')[2], rights);
        manager.reset();
    }
});

test('failed en passant removes the attacker, keeps its defender, and clears the opportunity', () => {
    const { manager } = game('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2');
    lose(manager, 'e5', 'd6');
    assert.equal(manager.chess.get('e5'), null);
    assert.deepEqual(manager.chess.get('d5'), { type: 'p', color: 'b' });
    assert.equal(manager.chess.get('d6'), null);
    assert.equal(manager.chess.fen().split(' ')[3], '-');
    manager.reset();
});

test('removal after real move history survives snapshots, draw inspection, and subsequent moves', () => {
    const { manager } = game();
    manager.attemptMove('e2', 'e4');
    manager.attemptMove('d7', 'd5');
    lose(manager, 'e4', 'd5');
    const fen = manager.chess.fen();
    assert.equal(manager.chess.get('e4'), null);
    assert.doesNotThrow(() => manager.getGameState());
    assert.doesNotThrow(() => manager.chess.history({ verbose: true }));
    assert.doesNotThrow(() => manager.chess.in_draw());
    assert.equal(manager.chess.fen(), fen);
    assert.ok(manager.attemptMove('g8', 'f6'));
    assert.equal(manager.chess.get('e4'), null);
    manager.reset();
});

test('computer attackers follow the same removal and check-response policy', { timeout: 5000 }, async () => {
    for (const fixture of [
        { fen: '4k3/8/8/8/8/8/4r3/3QK3 w - - 0 1', from: 'd1', to: 'e2' },
        { fen: '3qk3/4R3/8/8/8/8/8/4K3 b - - 0 1', from: 'd8', to: 'e7' }
    ]) {
        const { manager, bus, endings } = game(fixture.fen);
        const color = manager.chess.turn();
        manager.config.playerCount = 1;
        manager.config.players = ['w', 'b'].map(seat => ({ color: seat, name: seat, isAI: seat === color }));
        let searches = 0;
        manager.chessAI = {
            cancel() {},
            async chooseMove(fen) {
                if (searches++ === 0) return { from: fixture.from, to: fixture.to };
                return new Chess(fen).moves({ verbose: true }).find(move => move.piece === 'k' && !move.captured);
            }
        };
        try {
            const capture = new Promise(resolve => bus.on(GameEvent.CAPTURE_ATTEMPTED, resolve));
            bus.emit(GameEvent.BOARD_UPDATED, manager.getGameState());
            await capture;
            manager.resolveCapture({ attackerWins: false });
            assert.equal(manager.chess.get(fixture.from), null);
            assert.equal(manager.chess.turn(), color);
            assert.equal(manager.state, GameState.PLAYING);
            const reply = new Promise(resolve => bus.on(GameEvent.MOVE_MADE, resolve));
            await reply;
            assert.notEqual(manager.chess.turn(), color);
            assert.equal(manager.chess.in_check(), false);
            assert.equal(endings.length, 0);
        } finally { manager.reset(); }
    }
});

test('ordinary checkmate and genuine board draws still end the chess game', () => {
    for (const capture of [false, true]) {
        const { manager, endings } = game(capture
            ? '7k/6r1/5KQ1/8/8/8/8/8 w - - 0 1'
            : '7k/8/5KQ1/8/8/8/8/8 w - - 0 1');
        const result = manager.attemptMove('g6', 'g7');
        if (capture) {
            assert.equal(result.pending, true);
            manager.resolveCapture({ attackerWins: true });
        }
        assert.equal(manager.state, GameState.GAME_OVER);
        assert.equal(endings.length, 1);
        assert.equal(endings[0].isCheckmate, true);
        assert.equal(endings[0].forcedCheckmate, undefined);
        manager.reset();
    }
    const { manager, endings } = game('7k/8/7n/8/8/8/8/K1B5 w - - 0 1');
    assert.equal(manager.chess.game_over(), false);
    lose(manager, 'c1', 'h6');
    assert.equal(manager.state, GameState.GAME_OVER);
    assert.equal(endings[0].isDraw, true);
    assert.equal(endings[0].forcedCheckmate, undefined);
    manager.reset();
});
