import { BOARD_SIZE, SQUARE_SIZE, SQUARE_COUNT, GameEvent } from './Constants.js';

/**
 * Renders the chess board: squares, highlights, coordinates, pieces,
 * and valid-move indicators. Receives game state via EventBus.
 */
export class Board {
    constructor(canvas, skinManager, eventBus) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.skinManager = skinManager;
        this.eventBus = eventBus;

        // Rendering state
        this.boardState = null;
        this.selectedSquare = null;
        this.validMoves = [];
        this.lastMove = null;
        this.checkSquare = null;

        // ── Animation state ──
        this._animation = null; // { piece, fromX, fromY, toX, toY, start, duration, captured? }
        this._animFrameId = null;

        this._listen();
    }

    // ── Event wiring ─────────────────────────────────────

    _listen() {
        this.eventBus.on(GameEvent.BOARD_UPDATED, (state) => this._onBoardUpdated(state));
        this.eventBus.on(GameEvent.MOVE_MADE, (move) => this._onMoveMade(move));
    }

    _onMoveMade(move) {
        // Start slide animation from source to destination square
        const from = this._squareToCoords(move.from);
        const to = this._squareToCoords(move.to);
        this._animation = {
            piece: { type: move.piece, color: move.color },
            fromX: from.col * SQUARE_SIZE,
            fromY: from.row * SQUARE_SIZE,
            toX: to.col * SQUARE_SIZE,
            toY: to.row * SQUARE_SIZE,
            start: performance.now(),
            duration: 150,
            captured: move.captured ? {
                type: move.captured,
                color: move.color === 'w' ? 'b' : 'w',
                x: to.col * SQUARE_SIZE,
                y: to.row * SQUARE_SIZE
            } : null,
            hideSquare: move.to // hide the piece at destination during animation
        };
        this._animLoop();
    }

    _onBoardUpdated(gameState) {
        this.boardState = gameState.board;

        // Extract last move from history
        const history = gameState.moveHistory;
        this.lastMove = history.length > 0 ? history[history.length - 1] : null;

        // Find king square when in check
        this.checkSquare = gameState.isCheck
            ? this._findKing(gameState.board, gameState.turn)
            : null;

        this.render();
    }

    // ── Main render ──────────────────────────────────────

    render() {
        if (!this.boardState) return;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, BOARD_SIZE, BOARD_SIZE);

        this._drawSquares(ctx);
        this._drawLastMove(ctx);
        this._drawSelected(ctx);
        this._drawCheck(ctx);
        this._drawCoordinates(ctx);
        this._drawPieces(ctx);
        this._drawValidMoves(ctx);
        this._drawAnimation(ctx);
    }

    // ── Animation loop ───────────────────────────────────

    _animLoop() {
        if (!this._animation) return;
        this.render();
        const elapsed = performance.now() - this._animation.start;
        if (elapsed >= this._animation.duration) {
            this._animation = null;
            this.render();
            return;
        }
        this._animFrameId = requestAnimationFrame(() => this._animLoop());
    }

    _drawAnimation(ctx) {
        if (!this._animation) return;
        const a = this._animation;
        const elapsed = performance.now() - a.start;
        const t = Math.min(elapsed / a.duration, 1);
        // Ease-out quad
        const ease = 1 - (1 - t) * (1 - t);

        // Sliding piece
        const x = a.fromX + (a.toX - a.fromX) * ease;
        const y = a.fromY + (a.toY - a.fromY) * ease;
        this.skinManager.drawPiece(ctx, a.piece.type, a.piece.color, x, y, SQUARE_SIZE);

        // Captured piece: fade + shrink
        if (a.captured) {
            const fadeOut = 1 - ease;
            const scale = 0.5 + 0.5 * fadeOut;
            ctx.save();
            ctx.globalAlpha = fadeOut;
            const cx = a.captured.x + SQUARE_SIZE / 2;
            const cy = a.captured.y + SQUARE_SIZE / 2;
            ctx.translate(cx, cy);
            ctx.scale(scale, scale);
            this.skinManager.drawPiece(
                ctx, a.captured.type, a.captured.color,
                -SQUARE_SIZE / 2, -SQUARE_SIZE / 2, SQUARE_SIZE
            );
            ctx.restore();
        }
    }

    // ── Layer: squares ───────────────────────────────────

    _drawSquares(ctx) {
        const colors = this.skinManager.getBoardColors();
        for (let row = 0; row < SQUARE_COUNT; row++) {
            for (let col = 0; col < SQUARE_COUNT; col++) {
                ctx.fillStyle = (row + col) % 2 === 0 ? colors.light : colors.dark;
                ctx.fillRect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE);
            }
        }
    }

    // ── Layer: last move highlight ───────────────────────

    _drawLastMove(ctx) {
        if (!this.lastMove) return;
        const colors = this.skinManager.getBoardColors();
        ctx.fillStyle = colors.lastMove;

        const from = this._squareToCoords(this.lastMove.from);
        ctx.fillRect(from.col * SQUARE_SIZE, from.row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE);

        const to = this._squareToCoords(this.lastMove.to);
        ctx.fillRect(to.col * SQUARE_SIZE, to.row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE);
    }

    // ── Layer: selected square highlight ─────────────────

    _drawSelected(ctx) {
        if (!this.selectedSquare) return;
        const colors = this.skinManager.getBoardColors();
        const { row, col } = this._squareToCoords(this.selectedSquare);
        ctx.fillStyle = colors.selected;
        ctx.fillRect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE);
    }

    // ── Layer: check highlight (radial gradient) ─────────

    _drawCheck(ctx) {
        if (!this.checkSquare) return;
        const { row, col } = this._squareToCoords(this.checkSquare);
        const cx = col * SQUARE_SIZE + SQUARE_SIZE / 2;
        const cy = row * SQUARE_SIZE + SQUARE_SIZE / 2;

        const gradient = ctx.createRadialGradient(cx, cy, SQUARE_SIZE * 0.15, cx, cy, SQUARE_SIZE * 0.7);
        gradient.addColorStop(0, 'rgba(255, 0, 0, 0.6)');
        gradient.addColorStop(1, 'rgba(255, 0, 0, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE);
    }

    // ── Layer: coordinate labels ─────────────────────────

    _drawCoordinates(ctx) {
        const colors = this.skinManager.getBoardColors();
        const fontSize = Math.round(SQUARE_SIZE * 0.16);
        ctx.font = `bold ${fontSize}px "Segoe UI", sans-serif`;

        // File letters (a–h) — bottom-right corner of bottom row
        for (let col = 0; col < SQUARE_COUNT; col++) {
            const isLight = (7 + col) % 2 === 0;
            ctx.fillStyle = isLight ? colors.dark : colors.light;
            ctx.textAlign = 'right';
            ctx.textBaseline = 'bottom';
            ctx.fillText(
                String.fromCharCode(97 + col),
                (col + 1) * SQUARE_SIZE - 3,
                BOARD_SIZE - 3
            );
        }

        // Rank numbers (8–1) — top-left corner of left column
        for (let row = 0; row < SQUARE_COUNT; row++) {
            const isLight = (row) % 2 === 0;
            ctx.fillStyle = isLight ? colors.dark : colors.light;
            ctx.textAlign = 'left';
            ctx.textBaseline = 'top';
            ctx.fillText(
                String(SQUARE_COUNT - row),
                3,
                row * SQUARE_SIZE + 2
            );
        }
    }

    // ── Layer: pieces ────────────────────────────────────

    _drawPieces(ctx) {
        for (let row = 0; row < SQUARE_COUNT; row++) {
            for (let col = 0; col < SQUARE_COUNT; col++) {
                const piece = this.boardState[row][col];
                if (!piece) continue;
                // Hide the piece at the destination while animation is running
                if (this._animation && this._animation.hideSquare) {
                    const sq = this._coordsToSquare(row, col);
                    if (sq === this._animation.hideSquare) continue;
                }
                this.skinManager.drawPiece(
                    ctx,
                    piece.type,
                    piece.color,
                    col * SQUARE_SIZE,
                    row * SQUARE_SIZE,
                    SQUARE_SIZE
                );
            }
        }
    }

    // ── Layer: valid move indicators ─────────────────────

    _drawValidMoves(ctx) {
        const colors = this.skinManager.getBoardColors();

        for (const move of this.validMoves) {
            const { row, col } = this._squareToCoords(move.to);
            const cx = col * SQUARE_SIZE + SQUARE_SIZE / 2;
            const cy = row * SQUARE_SIZE + SQUARE_SIZE / 2;

            ctx.beginPath();
            if (move.captured) {
                // Capture: thick ring around square center
                ctx.arc(cx, cy, SQUARE_SIZE * 0.44, 0, Math.PI * 2);
                ctx.lineWidth = SQUARE_SIZE * 0.08;
                ctx.strokeStyle = colors.validMove;
                ctx.stroke();
            } else {
                // Normal move: small dot
                ctx.arc(cx, cy, SQUARE_SIZE * 0.15, 0, Math.PI * 2);
                ctx.fillStyle = colors.validMove;
                ctx.fill();
            }
        }
    }

    // ── Public API (for interaction in Step 3) ───────────

    setSelection(square, validMoves = []) {
        this.selectedSquare = square;
        this.validMoves = validMoves;
        this.render();
    }

    clearSelection() {
        this.selectedSquare = null;
        this.validMoves = [];
        this.render();
    }

    getSquareFromPixel(x, y) {
        const col = Math.floor(x / SQUARE_SIZE);
        const row = Math.floor(y / SQUARE_SIZE);
        if (col < 0 || col > 7 || row < 0 || row > 7) return null;
        return this._coordsToSquare(row, col);
    }

    // ── Coordinate helpers ───────────────────────────────

    _squareToCoords(square) {
        return {
            col: square.charCodeAt(0) - 97,   // a=0 .. h=7
            row: 8 - parseInt(square[1])       // 8→0 .. 1→7
        };
    }

    _coordsToSquare(row, col) {
        return String.fromCharCode(97 + col) + String(8 - row);
    }

    _findKing(board, color) {
        for (let row = 0; row < SQUARE_COUNT; row++) {
            for (let col = 0; col < SQUARE_COUNT; col++) {
                const piece = board[row][col];
                if (piece && piece.type === 'k' && piece.color === color) {
                    return this._coordsToSquare(row, col);
                }
            }
        }
        return null;
    }
}
