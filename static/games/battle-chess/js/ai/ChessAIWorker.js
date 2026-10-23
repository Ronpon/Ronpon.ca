/* Classic worker so the existing, locally vendored chess.js remains unchanged. */
importScripts('../../lib/chess.js');
const engine = import('./ChessAI.js');

self.onmessage = async ({ data }) => {
    try {
        const { findBestMove } = await engine;
        const move = await findBestMove(Chess, data.fen, data.difficulty);
        self.postMessage({ move });
    } catch (error) {
        self.postMessage({ error: String(error) });
    }
};
