// ── Game States ──────────────────────────────────────────
export const GameState = Object.freeze({
    SETUP: 'SETUP',
    PLAYING: 'PLAYING',
    MINIGAME: 'MINIGAME',
    GAME_OVER: 'GAME_OVER'
});

// ── Event Names ──────────────────────────────────────────
export const GameEvent = Object.freeze({
    STATE_CHANGED: 'stateChanged',
    MOVE_MADE: 'moveMade',
    CAPTURE_ATTEMPTED: 'captureAttempted',
    MINIGAME_START: 'minigameStart',
    MINIGAME_END: 'minigameEnd',
    GAME_OVER: 'gameOver',
    BOARD_UPDATED: 'boardUpdated',
    TURN_CHANGED: 'turnChanged',
    SETUP_COMPLETE: 'setupComplete',
    SKIN_CHANGED: 'skinChanged',
    PIECE_SELECTED: 'pieceSelected',
    PIECE_DESELECTED: 'pieceDeselected'
});

// ── Minigame Selection Modes ─────────────────────────────
export const MinigameMode = Object.freeze({
    RANDOM: 'random',
    ATTACKER_CHOICE: 'attackerChoice',
    DEFENDER_CHOICE: 'defenderChoice',
    SET_ORDER: 'setOrder'
});

// ── Board Dimensions ─────────────────────────────────────
export const BOARD_SIZE = 640;
export const SQUARE_COUNT = 8;
export const SQUARE_SIZE = BOARD_SIZE / SQUARE_COUNT;

// ── Piece Colors ─────────────────────────────────────────
export const WHITE = 'w';
export const BLACK = 'b';
