import { GameState, GameEvent, SQUARE_SIZE } from './Constants.js';

/**
 * Handles all canvas click interactions for piece selection and movement.
 * Delegates move execution to GameManager, rendering to Board.
 */
export class InputHandler {
    constructor(canvas, board, gameManager, eventBus) {
        this.canvas = canvas;
        this.board = board;
        this.gameManager = gameManager;
        this.eventBus = eventBus;
        this.checkWarning = null; // set by main.js after construction

        this.selectedSquare = null;
        this.validMoves = [];
        this.awaitingPromotion = null; // { from, to } when waiting for promotion choice

        this._onClick = this._onClick.bind(this);
        this.canvas.addEventListener('click', this._onClick);

        this.eventBus.on(GameEvent.BOARD_UPDATED, () => this._clearSelection());
    }

    _onClick(e) {
        if (this.gameManager.state !== GameState.PLAYING) return;
        if (this.awaitingPromotion) return; // block clicks while promotion popup is open

        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        const square = this.board.getSquareFromPixel(x, y);
        if (!square) return;

        // If a piece is already selected, try to move to the clicked square
        if (this.selectedSquare) {
            // Clicked the same square → deselect
            if (square === this.selectedSquare) {
                this._clearSelection();
                this.board.clearSelection();
                return;
            }

            // Check if clicked square is a valid move target
            const targetMove = this.validMoves.find(m => m.to === square);
            if (targetMove) {
                this._executeMove(this.selectedSquare, square, targetMove);
                return;
            }

            // Clicked a different own piece → re-select it
            const piece = this._getPieceAt(square);
            if (piece && piece.color === this.gameManager.chess.turn()) {
                this._selectSquare(square);
                return;
            }

            // Clicked an invalid square → deselect
            this._clearSelection();
            this.board.clearSelection();
            return;
        }

        // No piece selected yet — try to select one
        const piece = this._getPieceAt(square);
        if (piece && piece.color === this.gameManager.chess.turn()) {
            this._selectSquare(square);
        }
    }

    _selectSquare(square) {
        this.selectedSquare = square;
        this.validMoves = this.gameManager.getValidMoves(square);
        this.board.setSelection(square, this.validMoves);
        this.eventBus.emit(GameEvent.PIECE_SELECTED, { square, validMoves: this.validMoves });
    }

    _clearSelection() {
        this.selectedSquare = null;
        this.validMoves = [];
    }

    _executeMove(from, to, targetMove) {
        // Check if this is a promotion move
        if (targetMove.promotion) {
            this.awaitingPromotion = { from, to };
            this.eventBus.emit('promotionRequired', { from, to });
            return;
        }

        // Check warning: in check + capture + minigames enabled
        const inCheck = this.gameManager.chess.in_check();
        const isCapture = !!targetMove.captured;
        const minigamesOn = this.gameManager.config.selectedMinigames.length > 0;

        if (inCheck && isCapture && minigamesOn && this.checkWarning) {
            this.checkWarning.show().then(fight => {
                if (fight) {
                    this.gameManager.attemptMove(from, to);
                    this._clearSelection();
                    this.board.clearSelection();
                } else {
                    // Player chose "Back" — just deselect
                    this._clearSelection();
                    this.board.clearSelection();
                }
            });
            return;
        }

        this.gameManager.attemptMove(from, to);
        this._clearSelection();
        this.board.clearSelection();
    }

    /**
     * Called by the promotion dialog when the player picks a piece.
     */
    resolvePromotion(choice) {
        if (!this.awaitingPromotion) return;
        const { from, to } = this.awaitingPromotion;
        this.awaitingPromotion = null;
        this.gameManager.attemptMove(from, to, choice);
        this._clearSelection();
        this.board.clearSelection();
    }

    cancelPromotion() {
        this.awaitingPromotion = null;
        this._clearSelection();
        this.board.clearSelection();
    }

    _getPieceAt(square) {
        const board = this.gameManager.chess.board();
        const col = square.charCodeAt(0) - 97;
        const row = 8 - parseInt(square[1]);
        return board[row][col];
    }
}
