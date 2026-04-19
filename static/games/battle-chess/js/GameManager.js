import { GameState, GameEvent, MinigameMode, MinigameAdvantage } from './Constants.js';

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
            attackerLosesPiece: false
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
    }

    // ── State transitions ────────────────────────────────
    setState(newState) {
        const oldState = this.state;
        this.state = newState;
        this.eventBus.emit(GameEvent.STATE_CHANGED, { from: oldState, to: newState });
        console.log(`[GameManager] State: ${oldState} → ${newState}`);
    }

    // ── Game lifecycle ───────────────────────────────────
    startGame(config) {
        if (config) {
            Object.assign(this.config, config);
        }
        this.chess.reset();
        this.pendingMove = null;
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
    attemptMove(from, to, promotion = 'q') {
        if (this.state !== GameState.PLAYING) return null;

        const validMoves = this.chess.moves({ square: from, verbose: true });
        const targetMove = validMoves.find(m => m.to === to) || null;

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
        if (this.state !== GameState.PLAYING) return [];
        return this.chess.moves({ square, verbose: true });
    }

    getCurrentPlayer() {
        const turn = this.chess.turn();
        return this.config.players.find(p => p.color === turn);
    }

    reset() {
        this.chess.reset();
        this.pendingMove = null;
        this.setState(GameState.SETUP);
    }
}
