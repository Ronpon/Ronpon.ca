const VALUES = { p: 100, n: 320, b: 335, r: 500, q: 900, k: 0 };
const MATE = 100000;
const STOP = Symbol('search stopped');

export const CHESS_LEVELS = Object.freeze({
    easy: Object.freeze({ depth: 1, nodes: 1000, time: 100 }),
    medium: Object.freeze({ depth: 3, nodes: 5000, time: 350 }),
    hard: Object.freeze({ depth: 5, nodes: 20000, time: 1000 })
});

function evaluate(chess) {
    let score = 0;
    const bishops = { w: 0, b: 0 };
    const board = chess.board();
    let material = 0;
    for (const row of board) {
        for (const piece of row) if (piece && piece.type !== 'p') material += VALUES[piece.type];
    }
    for (let row = 0; row < 8; row++) {
        for (let file = 0; file < 8; file++) {
            const piece = board[row][file];
            if (!piece) continue;
            const rank = piece.color === 'w' ? 7 - row : row;
            const center = 3.5 - (Math.abs(file - 3.5) + Math.abs(row - 3.5)) / 2;
            let position = 0;
            if (piece.type === 'p') position = rank * 9 + center * 5;
            if (piece.type === 'n') position = center * 22 - (rank === 0 ? 12 : 0);
            if (piece.type === 'b') { position = center * 12; bishops[piece.color]++; }
            if (piece.type === 'r') position = rank === 6 ? 24 : rank * 2;
            if (piece.type === 'q') position = center * 4;
            if (piece.type === 'k') {
                position = material <= 1800 ? center * 20
                    : -rank * 12 + (rank === 0 && (file === 2 || file === 6) ? 35 : 0);
            }
            score += (piece.color === 'w' ? 1 : -1) * (VALUES[piece.type] + position);
        }
    }
    if (bishops.w >= 2) score += 25;
    if (bishops.b >= 2) score -= 25;
    return chess.turn() === 'w' ? score : -score;
}

function movePriority(move) {
    return (move.captured ? 10 * VALUES[move.captured] - VALUES[move.piece] : 0)
        + (move.promotion ? VALUES[move.promotion] : 0)
        + (move.san.includes('+') || move.san.includes('#') ? 30 : 0);
}

const moveKey = move => `${move.from}${move.to}${move.promotion || ''}`;
const plainMove = move => move ? {
    from: move.from, to: move.to, ...(move.promotion ? { promotion: move.promotion } : {})
} : null;

/** Search a private position. The generator yields regularly for the no-worker fallback. */
export async function findBestMove(ChessConstructor, fen, difficulty = 'medium', options = {}) {
    const chess = new ChessConstructor(fen);
    if (chess.game_over()) return null;
    const level = CHESS_LEVELS[difficulty] || CHESS_LEVELS.medium;
    const now = options.now || (() => performance.now());
    const random = options.random || Math.random;
    const started = now();
    const deadline = started + (options.timeLimit ?? level.time);
    const cancelled = options.cancelled || (() => false);
    const pause = options.pause || (() => new Promise(resolve => setTimeout(resolve, 0)));
    let sliceStarted = started;
    let nodes = 0;
    let bestMove = null;
    let completedScores = [];

    function* checkpoint() {
        if (cancelled() || now() >= deadline || ++nodes > level.nodes) throw STOP;
        if (now() - sliceStarted >= 10) {
            yield;
            sliceStarted = now();
            if (cancelled() || sliceStarted >= deadline) throw STOP;
        }
    }

    function* search(depth, alpha, beta, ply) {
        yield* checkpoint();
        const moves = chess.moves({ verbose: true });
        if (!moves.length) return chess.in_check() ? -MATE + ply : 0;
        if (chess.insufficient_material() || Number(chess.fen().split(' ')[4]) >= 100
            || chess.in_threefold_repetition()) return 0;
        if (depth <= 0) return evaluate(chess);
        moves.sort((a, b) => movePriority(b) - movePriority(a));
        let best = -Infinity;
        for (const move of moves) {
            chess.move(move);
            let score;
            try { score = -(yield* search(depth - 1, -beta, -alpha, ply + 1)); }
            finally { chess.undo(); }
            best = Math.max(best, score);
            alpha = Math.max(alpha, score);
            if (alpha >= beta) break;
        }
        return best;
    }

    const rootMoves = chess.moves({ verbose: true }).sort((a, b) => movePriority(b) - movePriority(a));
    bestMove = rootMoves[0]; // A legal answer is available even on a very slow device.

    function* deepen() {
        for (let depth = 1; depth <= level.depth; depth++) {
            const scores = [];
            let alpha = -Infinity;
            for (const move of rootMoves) {
                yield* checkpoint();
                chess.move(move);
                let score;
                try { score = -(yield* search(depth - 1, -Infinity, -alpha, 1)); }
                finally { chess.undo(); }
                scores.push({ move, score });
                alpha = Math.max(alpha, score);
            }
            scores.sort((a, b) => b.score - a.score);
            completedScores = scores;
            bestMove = scores[0].move;
            const ordering = new Map(scores.map((entry, index) => [moveKey(entry.move), index]));
            rootMoves.sort((a, b) => ordering.get(moveKey(a)) - ordering.get(moveKey(b)));
            if (scores[0].score >= MATE - 100) return;
        }
    }

    const work = deepen();
    try {
        while (!work.next().done) await pause();
    } catch (error) {
        if (error !== STOP) throw error;
    }
    if (cancelled()) return null;
    // Easy occasionally picks another reasonable one-ply move instead of the best.
    if (difficulty === 'easy' && completedScores.length && random() < 0.3) {
        const choices = completedScores.filter(entry => entry.score >= completedScores[0].score - 100).slice(0, 5);
        bestMove = choices[Math.min(choices.length - 1, Math.floor(random() * choices.length))].move;
    }
    return plainMove(bestMove);
}

/** Runs searches off the UI thread, with a yielding fallback for unsupported workers. */
export class ChessAI {
    constructor(ChessConstructor = globalThis.Chess) {
        this.ChessConstructor = ChessConstructor;
        this.generation = 0;
        this.worker = null;
        this.finish = null;
    }

    cancel() {
        this.generation++;
        this.worker?.terminate();
        this.worker = null;
        if (this.finish) this.finish(null);
        this.finish = null;
    }

    chooseMove(fen, difficulty = 'medium') {
        this.cancel();
        const generation = this.generation;
        return new Promise(resolve => {
            let done = false;
            let watchdog;
            let fallingBack = false;
            const finish = move => {
                if (done) return;
                done = true;
                clearTimeout(watchdog);
                this.worker?.terminate();
                this.worker = null;
                this.finish = null;
                resolve(generation === this.generation ? move : null);
            };
            this.finish = finish;
            const fallback = () => {
                if (done || fallingBack) return;
                fallingBack = true;
                clearTimeout(watchdog);
                this.worker?.terminate();
                this.worker = null;
                findBestMove(this.ChessConstructor, fen, difficulty, {
                    cancelled: () => done || generation !== this.generation,
                    timeLimit: difficulty === 'hard' ? 500 : undefined
                }).then(finish).catch(error => {
                    console.warn('[ChessAI] Search failed:', error);
                    // Keep solo play usable even if an optional search feature fails.
                    const board = new this.ChessConstructor(fen);
                    finish(plainMove(board.moves({ verbose: true })[0]));
                });
            };
            try {
                if (typeof Worker === 'undefined') { fallback(); return; }
                this.worker = new Worker(new URL('./ChessAIWorker.js', import.meta.url));
                this.worker.onmessage = event => event.data.error ? fallback() : finish(event.data.move);
                this.worker.onerror = event => { event.preventDefault(); fallback(); };
                this.worker.postMessage({ fen, difficulty });
                watchdog = setTimeout(fallback, 2500);
            } catch { fallback(); }
        });
    }
}
