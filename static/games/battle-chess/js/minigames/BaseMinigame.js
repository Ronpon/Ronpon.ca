/**
 * Abstract base class for all minigames.
 * Extend this class and implement the required methods to create a new minigame.
 *
 * Lifecycle:
 *   1. constructor() — define static metadata
 *   2. init(container, config) — set up DOM/canvas, bind keys
 *   3. start() — begin gameplay loop
 *   4. (game plays…)
 *   5. end({ attackerWins, tie }) — called by subclass when game concludes
 *   6. destroy() — clean up DOM, listeners, animation frames
 */
const AI_SETTINGS = {
    easy: { reaction: [550, 950], mash: [260, 380], dodgeInterval: 0.36, dodgeHorizon: 0.4, memoryLimit: 16, memoryRecall: 0.55, cardDelay: [700, 1100] },
    medium: { reaction: [300, 550], mash: [145, 220], dodgeInterval: 0.2, dodgeHorizon: 0.7, memoryLimit: 32, memoryRecall: 0.82, cardDelay: [450, 750] },
    hard: { reaction: [170, 320], mash: [85, 125], dodgeInterval: 0.1, dodgeHorizon: 1, memoryLimit: 52, memoryRecall: 1, cardDelay: [280, 500] }
};

export class BaseMinigame {
    constructor() {
        // ── Metadata (override in subclass) ──────────────
        this.id = 'base';              // unique string id
        this.name = 'Base Minigame';   // display name
        this.thumbnail = '🎮';         // emoji or image path
        this.description = '';          // first-time explanation text
        this.category = 'Other';       // category for setup grouping
        this.controls = {
            player1: '',               // e.g. "WASD to move"
            player2: ''                // e.g. "IJKL to move"
        };

        // ── Runtime state ────────────────────────────────
        this.container = null;         // DOM element to render into
        this.players = null;           // [{ name, icon, color }, { name, icon, color }]
        this.attackerColor = null;     // 'w' or 'b'
        this.advantage = 'attacker';   // 'attacker' | 'defender' | 'none'
        this.onEnd = null;             // callback: ({ attackerWins: bool, tie: bool }) => void
        this._animFrameId = null;
        this._destroyed = false;
        this._ended = false;
        this._timers = new Set();
    }

    /**
     * Set up the minigame inside the given container.
     * Called once before start().
     * @param {HTMLElement} container - DOM element to render into
     * @param {Object} config
     * @param {Array} config.players - [player1, player2] objects
     * @param {string} config.attackerColor - 'w' or 'b'
     * @param {string} config.advantage - 'attacker', 'defender', or 'none'
     * @param {string} config.aiDifficulty - 'easy', 'medium', or 'hard'
     * @param {Function} config.onEnd - callback when game ends
     */
    init(container, { players, attackerColor, advantage, onEnd, aiDifficulty = 'medium' }) {
        this.clearTimers();
        if (this._animFrameId !== null) cancelAnimationFrame(this._animFrameId);
        this._animFrameId = null;
        this.container = container;
        this.players = players;
        this.attackerColor = attackerColor;
        this.advantage = advantage || 'attacker';
        this.onEnd = onEnd;
        this._destroyed = false;
        this._ended = false;
        this.aiDifficulty = Object.hasOwn(AI_SETTINGS, aiDifficulty) ? aiDifficulty : 'medium';
        this.aiSettings = AI_SETTINGS[this.aiDifficulty];
    }

    /**
     * Start gameplay. Called after init() and after any explanation screen.
     * Override to begin your game loop.
     */
    start() {
        throw new Error(`${this.constructor.name} must implement start()`);
    }

    /**
     * Call this from your subclass when the minigame concludes.
     * @param {Object} result
     * @param {boolean} result.attackerWins - true if attacker won
     * @param {boolean} result.tie - true if it's a tie (both eliminated)
     */
    end(result) {
        if (this._destroyed || this._ended) return;
        this._ended = true;
        this.clearTimers();
        if (this._animFrameId) cancelAnimationFrame(this._animFrameId);
        this._animFrameId = null;
        if (this.onEnd) {
            this.onEnd(result);
        }
    }

    /**
     * Clean up everything. Cancel animation frames, remove listeners, clear DOM.
     * Override and call super.destroy() for additional cleanup.
     */
    destroy() {
        this._destroyed = true;
        this.clearTimers();
        if (this._animFrameId) {
            cancelAnimationFrame(this._animFrameId);
            this._animFrameId = null;
        }
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    // ── Helpers for subclasses ───────────────────────────

    /** Get the attacker player object (index 0 or 1). */
    getAttacker() {
        return this.attackerColor === 'w' ? this.players[0] : this.players[1];
    }

    /** Get the defender player object (index 0 or 1). */
    getDefender() {
        return this.attackerColor === 'w' ? this.players[1] : this.players[0];
    }

    /** Request an animation frame, tracked for auto-cleanup. */
    requestFrame(callback) {
        if (this._destroyed || this._ended) return null;
        this._animFrameId = requestAnimationFrame(() => {
            this._animFrameId = null;
            if (!this._destroyed && !this._ended) callback();
        });
        return this._animFrameId;
    }

    /** Players keep the same White/Black seat in every battle. */
    isAI(playerIndex) {
        return this.players?.[playerIndex]?.isAI === true;
    }

    randomDelay(range) {
        return range[0] + Math.random() * (range[1] - range[0]);
    }

    /** Timers stop on a result, teardown, or a new initialization. */
    setTimer(callback, delay) {
        if (this._destroyed || this._ended) return null;
        const timer = setTimeout(() => {
            this._timers.delete(timer);
            if (!this._destroyed && !this._ended) callback();
        }, delay);
        this._timers.add(timer);
        return timer;
    }

    setRepeatingTimer(callback, delay) {
        if (this._destroyed || this._ended) return null;
        const timer = setInterval(() => {
            if (!this._destroyed && !this._ended) callback();
        }, delay);
        this._timers.add(timer);
        return timer;
    }

    clearTimer(timer) {
        clearTimeout(timer);
        clearInterval(timer);
        this._timers.delete(timer);
    }

    clearTimers() {
        for (const timer of this._timers) {
            clearTimeout(timer);
            clearInterval(timer);
        }
        this._timers.clear();
    }
}
