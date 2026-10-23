import { GameState, GameEvent, MinigameMode, MinigameAdvantage } from './Constants.js';
import { ChessAI } from './ai/ChessAI.js';

const AI_MOVE = Symbol('computer move');

/**
 * Central game state machine. Owns the chess.js instance and all game config.
 * States: SETUP → PLAYING ↔ MINIGAME → GAME_OVER
 */
export class GameManager {
    constructor(eventBus) {
        this.eventBus = eventBus;
        this.state = GameState.SETUP;
        this.chess = new Chess(); // chess.js global (loaded via <script>)
        this.pendingMove = null;
        this.pendingMoveInCheck = false; // was attacker in check when capture was attempted?
        this.chessAI = new ChessAI(globalThis.Chess);
        this.aiThinking = false;
        this._aiTimer = null;
        this._aiGeneration = 0;

        // ── Game configuration (populated during setup) ──
        this.config = {
            playerCount: 2,
            players: [
                { name: 'Player 1', icon: null, color: 'w' },
                { name: 'Player 2', icon: null, color: 'b' }
            ],
            selectedMinigames: [],
            minigameMode: MinigameMode.RANDOM,
            minigameAdvantage: MinigameAdvantage.ATTACKER,
            attackerLosesPiece: false,
            chessDifficulty: 'medium',
            aiDifficulty: 'medium'
        };

        // ── Minigame session tracking ──
        this.minigameState = {
            currentIndex: 0,            // for Set Order cycling
            firstTimePlayed: new Set()   // which minigames have shown their explanation
        };

        this._setupEventListeners();
    }

    // ── Event wiring ─────────────────────────────────────
    _setupEventListeners() {
        this.eventBus.on(GameEvent.SETUP_COMPLETE, (config) => this.startGame(config));
        this.eventBus.on(GameEvent.MINIGAME_END, (result) => this.resolveCapture(result));
        this.eventBus.on(GameEvent.BOARD_UPDATED, () => this._scheduleAI());
    }

    // ── State transitions ────────────────────────────────
    setState(newState) {
        if (newState !== GameState.PLAYING) this._cancelAI();
        const oldState = this.state;
        this.state = newState;
        this.eventBus.emit(GameEvent.STATE_CHANGED, { from: oldState, to: newState });
        console.log(`[GameManager] State: ${oldState} → ${newState}`);
    }

    // ── Game lifecycle ───────────────────────────────────
    startGame(config) {
        this._cancelAI();
        if (config) {
            Object.assign(this.config, config);
        }
        // Keep both seats in color order, including when the human chooses Black.
        if (this.config.playerCount === 1 && !this.config.players.some(player => player.isAI)) {
            const computerColor = this.config.humanColor === 'b' ? 'w' : 'b';
            this.config.players = ['w', 'b'].map(color => ({
                ...(this.config.players.find(player => player.color === color) || { color, name: 'Player' }),
                isAI: color === computerColor,
                ...(color === computerColor ? { name: 'Computer' } : {})
            }));
        }
        this.chess.reset();
        this.pendingMove = null;
        this.pendingMoveInCheck = false;
        this.minigameState.currentIndex = 0;
        this.minigameState.firstTimePlayed.clear();
        this.setState(GameState.PLAYING);
        this.eventBus.emit(GameEvent.BOARD_UPDATED, this.getGameState());
        console.log('[GameManager] Game started.');
    }

    /**
     * Returns a serializable snapshot of the full game state.
     * This is the object that would be sent over a network for online play.
     */
    getGameState() {
        return {
            fen: this.chess.fen(),
            board: this.chess.board(),
            turn: this.chess.turn(),
            isCheck: this.chess.in_check(),
            isCheckmate: this.chess.in_checkmate(),
            isStalemate: this.chess.in_stalemate(),
            isDraw: this.chess.in_draw(),
            isGameOver: this.chess.game_over(),
            moveHistory: this.chess.history({ verbose: true }),
            config: this.config
        };
    }

    // ── Move handling ────────────────────────────────────
    /**
     * Attempt a move from one square to another.
     * If it's a capture and minigames are enabled, the move is held pending
     * and a CAPTURE_ATTEMPTED event is emitted instead.
     * Returns the executed move, a {pending} object, or null if invalid.
     */
    attemptMove(from, to, promotion = 'q', source = null) {
        if (this.online) return this.online.attemptMove(from, to, promotion);
        if (this.state !== GameState.PLAYING) return null;
        if (this.isAITurn() && source !== AI_MOVE) return null;

        const validMoves = this.chess.moves({ square: from, verbose: true });
        const targetMove = validMoves.find(m => m.to === to && (!m.promotion || m.promotion === promotion)) || null;

        if (!targetMove) return null;

        // Capture with minigames enabled → trigger minigame
        if (targetMove.captured && this.config.selectedMinigames.length > 0) {
            this.pendingMove = targetMove;
            this.pendingMoveInCheck = this.chess.in_check();
            this.setState(GameState.MINIGAME);
            this.eventBus.emit(GameEvent.CAPTURE_ATTEMPTED, {
                move: targetMove,
                attackerColor: this.chess.turn(),
                from,
                to
            });
            return { pending: true, move: targetMove };
        }

        // Normal move (no capture, or no minigames)
        const executedMove = this.chess.move({
            from,
            to,
            promotion: targetMove.promotion ? promotion : undefined
        });

        if (executedMove) {
            this.eventBus.emit(GameEvent.MOVE_MADE, executedMove);
            this.eventBus.emit(GameEvent.BOARD_UPDATED, this.getGameState());
            this._checkGameEnd();
        }

        return executedMove;
    }

    // ── Minigame outcome resolution ─────────────────────
    resolveCapture(result) {
        if (!this.pendingMove) return;

        const move = this.pendingMove;
        this.pendingMove = null;

        if (result.attackerWins) {
            // Attacker wins → execute the capture normally
            const executedMove = this.chess.move({
                from: move.from,
                to: move.to,
                promotion: move.promotion || 'q'
            });
            if (executedMove) {
                this.eventBus.emit(GameEvent.MOVE_MADE, executedMove);
            }
        } else {
            // Attacker lost the minigame
            if (this.pendingMoveInCheck) {
                // Was in check and failed to capture → checkmate
                this.setState(GameState.GAME_OVER);
                this.eventBus.emit(GameEvent.GAME_OVER, {
                    ...this.getGameState(),
                    isCheckmate: true,
                    forcedCheckmate: true // lost minigame while in check
                });
                this.pendingMoveInCheck = false;
                return;
            }
            if (this.config.attackerLosesPiece) {
                // A failed king attack, or removing a pinned attacker, loses the game.
                // Preserve the valid position for the final board instead of loading
                // a FEN with a missing or exposed king for the next player.
                const testBoard = new Chess(this.chess.fen());
                testBoard.remove(move.from);
                if (move.piece === 'k' || testBoard.in_check()) {
                    this.setState(GameState.GAME_OVER);
                    this.eventBus.emit(GameEvent.GAME_OVER, {
                        ...this.getGameState(), isCheckmate: true, forcedCheckmate: true
                    });
                    this.pendingMoveInCheck = false;
                    return;
                }
                this.chess.remove(move.from);
            }
            // Turn passes to the other player
            this._switchTurn();
        }

        this.pendingMoveInCheck = false;

        this.setState(GameState.PLAYING);
        this.eventBus.emit(GameEvent.BOARD_UPDATED, this.getGameState());
        this._checkGameEnd();
    }

    // ── Helpers ──────────────────────────────────────────
    _switchTurn() {
        const fen = this.chess.fen();
        const parts = fen.split(' ');
        parts[1] = parts[1] === 'w' ? 'b' : 'w';
        parts[3] = '-'; // clear en passant (no longer valid after forced turn switch)
        this.chess.load(parts.join(' '));
    }

    _checkGameEnd() {
        if (this.chess.game_over()) {
            this.setState(GameState.GAME_OVER);
            this.eventBus.emit(GameEvent.GAME_OVER, this.getGameState());
        }
    }

    getValidMoves(square) {
        if (this.online && !this.online.canMove()) return [];
        if (this.state !== GameState.PLAYING) return [];
        if (this.isAITurn()) return [];
        return this.chess.moves({ square, verbose: true });
    }

    isAITurn() {
        return !this.online && this.config.playerCount === 1 && !!this.getCurrentPlayer()?.isAI;
    }

    canHumanMove() {
        return this.state === GameState.PLAYING
            && (this.online ? this.online.canMove() : !this.isAITurn());
    }

    _cancelAI() {
        this._aiGeneration++;
        clearTimeout(this._aiTimer);
        this._aiTimer = null;
        this.aiThinking = false;
        this.chessAI.cancel();
    }

    _scheduleAI() {
        this._cancelAI();
        if (this.state !== GameState.PLAYING || !this.isAITurn() || this.chess.game_over()) return;
        const generation = this._aiGeneration;
        const fen = this.chess.fen();
        this.aiThinking = true;
        this._aiTimer = setTimeout(async () => {
            this._aiTimer = null;
            const move = await this.chessAI.chooseMove(fen, this.config.chessDifficulty);
            if (generation !== this._aiGeneration || !move || this.state !== GameState.PLAYING
                || !this.isAITurn() || this.chess.fen() !== fen) return;
            this.aiThinking = false;
            // AI captures follow the same pending-move and minigame path as human moves.
            this.attemptMove(move.from, move.to, move.promotion || 'q', AI_MOVE);
        }, 250);
    }

    getCurrentPlayer() {
        const turn = this.chess.turn();
        return this.config.players.find(p => p.color === turn);
    }

    reset() {
        this._cancelAI();
        this.chess.reset();
        this.pendingMove = null;
        this.pendingMoveInCheck = false;
        this.setState(GameState.SETUP);
    }
}
