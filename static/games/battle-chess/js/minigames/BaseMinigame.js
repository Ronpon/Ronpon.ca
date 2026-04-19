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
    }

    /**
     * Set up the minigame inside the given container.
     * Called once before start().
     * @param {HTMLElement} container - DOM element to render into
     * @param {Object} config
     * @param {Array} config.players - [player1, player2] objects
     * @param {string} config.attackerColor - 'w' or 'b'
     * @param {string} config.advantage - 'attacker', 'defender', or 'none'
     * @param {Function} config.onEnd - callback when game ends
     */
    init(container, { players, attackerColor, advantage, onEnd }) {
        this.container = container;
        this.players = players;
        this.attackerColor = attackerColor;
        this.advantage = advantage || 'attacker';
        this.onEnd = onEnd;
        this._destroyed = false;
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
        if (this._destroyed) return;
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
        this._animFrameId = requestAnimationFrame(callback);
        return this._animFrameId;
    }
}
