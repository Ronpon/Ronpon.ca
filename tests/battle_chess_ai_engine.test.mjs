import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { findBestMove, ChessAI, CHESS_LEVELS } from '../static/games/battle-chess/js/ai/ChessAI.js';
import { GameManager } from '../static/games/battle-chess/js/GameManager.js';
import { EventBus } from '../static/games/battle-chess/js/EventBus.js';
import { GameEvent, GameState } from '../static/games/battle-chess/js/Constants.js';

const require = createRequire(import.meta.url);
const { Chess } = require('../static/games/battle-chess/lib/chess.js');
globalThis.Chess = Chess;
const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const solo = (computer = 'b') => ({
    playerCount: 1,
    chessDifficulty: 'easy',
    selectedMinigames: [],
    players: ['w', 'b'].map(color => ({ color, name: color === computer ? 'Computer' : 'Human', isAI: color === computer }))
});

test('every difficulty returns a legal move without changing the source position', async () => {
    const position = new Chess();
    position.move('e4');
    const fen = position.fen();
    for (const difficulty of Object.keys(CHESS_LEVELS)) {
        const move = await findBestMove(Chess, fen, difficulty, { random: () => 0.9 });
        assert.ok(new Chess(fen).move(move), difficulty);
        assert.equal(position.fen(), fen);
    }
    assert.ok(CHESS_LEVELS.hard.depth > CHESS_LEVELS.medium.depth);
    assert.ok(CHESS_LEVELS.medium.depth > CHESS_LEVELS.easy.depth);
});

test('the search finds mate, valuable captures, and queen promotions', async () => {
    const mate = new Chess('7k/8/5KQ1/8/8/8/8/8 w - - 0 1');
    mate.move(await findBestMove(Chess, mate.fen(), 'hard'));
    assert.equal(mate.in_checkmate(), true);
    const capture = new Chess('4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1');
    const winningMove = await findBestMove(Chess, capture.fen(), 'medium');
    assert.equal(capture.move(winningMove).captured, 'q');
    const promotion = new Chess('7k/P7/8/8/8/8/8/7K w - - 0 1');
    const promotingMove = await findBestMove(Chess, promotion.fen(), 'medium');
    assert.equal(promotingMove.promotion, 'q');
    assert.ok(promotion.move(promotingMove));
});

test('finished games return no move and fallback cancellation resolves promptly', async () => {
    assert.equal(await findBestMove(Chess, '7k/5K2/6Q1/8/8/8/8/8 b - - 0 1', 'hard'), null);
    const ai = new ChessAI(Chess);
    const pending = ai.chooseMove(new Chess().fen(), 'hard');
    ai.cancel();
    assert.equal(await pending, null);
});

test('solo blocks human control of AI pieces and routes AI captures into battles', async () => {
    const bus = new EventBus();
    const manager = new GameManager(bus);
    manager.startGame({ ...solo('w'), selectedMinigames: ['highest-card'] });
    manager.chess.load('4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1');
    let capture;
    bus.on(GameEvent.CAPTURE_ATTEMPTED, data => { capture = data; });
    bus.emit(GameEvent.BOARD_UPDATED, manager.getGameState());
    assert.equal(manager.canHumanMove(), false);
    assert.equal(manager.attemptMove('d2', 'd5'), null);
    assert.deepEqual(manager.getValidMoves('d2'), []);
    await delay(700);
    assert.equal(manager.state, GameState.MINIGAME);
    assert.equal(capture.move.captured, 'q');
    assert.equal(manager.chess.get('d5').type, 'q');
    manager.resolveCapture({ attackerWins: true });
    assert.equal(manager.chess.get('d5').type, 'r');
    assert.equal(manager.chess.turn(), 'b');
    assert.equal(manager.canHumanMove(), true);
    manager.reset();
});

test('a human playing Black gets an automatic opening and a reply after battle resolution', async () => {
    const bus = new EventBus();
    const manager = new GameManager(bus);
    manager.startGame(solo('w'));
    await delay(700);
    assert.equal(manager.chess.history().length, 1);
    assert.equal(manager.chess.turn(), 'b');
    manager.config.selectedMinigames = ['highest-card'];
    manager.chess.load('4k3/8/8/3q4/8/8/3R4/4K3 b - - 0 1');
    assert.equal(manager.attemptMove('d5', 'd2').pending, true);
    manager.resolveCapture({ attackerWins: false });
    await delay(700);
    assert.equal(manager.state, GameState.MINIGAME);
    assert.equal(manager.pendingMove.color, 'w');
    manager.reset();
});

test('reset, two-player restart, and online play discard in-flight AI answers', async () => {
    const bus = new EventBus();
    const manager = new GameManager(bus);
    let resolveSearch;
    let workerCancelled = 0;
    manager.chessAI = {
        cancel: () => { workerCancelled++; },
        chooseMove: () => new Promise(resolve => { resolveSearch = resolve; })
    };
    manager.startGame(solo('w'));
    await delay(300);
    manager.reset();
    manager.startGame({ ...solo('w'), playerCount: 2 });
    resolveSearch({ from: 'e2', to: 'e4' });
    await delay(10);
    assert.equal(manager.chess.history().length, 0);
    assert.equal(manager.canHumanMove(), true);
    manager.startGame(solo('w'));
    await delay(300);
    manager.online = { canMove: () => false };
    manager.setState(GameState.SETUP);
    resolveSearch({ from: 'e2', to: 'e4' });
    await delay(10);
    assert.equal(manager.chess.history().length, 0);
    assert.equal(manager.aiThinking, false);
    assert.ok(workerCancelled >= 3);
    manager.reset();
});

test('capture promotions retain the selected piece and failed king battles keep a valid board', () => {
    const manager = new GameManager(new EventBus());
    manager.startGame({ playerCount: 2, selectedMinigames: ['highest-card'], attackerLosesPiece: true });
    manager.chess.load('1r5k/P7/8/8/8/8/8/7K w - - 0 1');
    assert.equal(manager.attemptMove('a7', 'b8', 'n').pending, true);
    manager.resolveCapture({ attackerWins: true });
    assert.equal(manager.chess.get('b8').type, 'n');
    manager.startGame({ playerCount: 2, selectedMinigames: ['highest-card'], attackerLosesPiece: true });
    manager.chess.load('7k/8/8/8/8/8/1p6/1K6 w - - 0 1');
    assert.equal(manager.attemptMove('b1', 'b2').pending, true);
    manager.resolveCapture({ attackerWins: false });
    assert.equal(manager.state, GameState.GAME_OVER);
    assert.equal(manager.chess.get('b1').type, 'k');
    manager.reset();
});
