import { GameEvent, MinigameMode } from './Constants.js';

/**
 * Orchestrates the full minigame flow:
 *   capture attempted → (chooser?) → (explanation?) → play → (tie? replay) → resolve
 *
 * Owns the registry of available minigame classes and the MinigameScreen UI.
 */
export class MinigameManager {
    constructor(eventBus, gameManager) {
        this.eventBus = eventBus;
        this.gameManager = gameManager;

        // Registry: { id → MinigameClass (extends BaseMinigame) }
        this._registry = new Map();

        // Currently running minigame instance
        this._activeGame = null;

        // Pending capture context
        this._captureCtx = null;

        this.eventBus.on(GameEvent.CAPTURE_ATTEMPTED, (ctx) => this._onCapture(ctx));
    }

    // ── Registration ─────────────────────────────────────

    /**
     * Register a minigame class. Called at init time.
     * @param {typeof BaseMinigame} MinigameClass
     */
    register(MinigameClass) {
        const instance = new MinigameClass();
        this._registry.set(instance.id, {
            id: instance.id,
            name: instance.name,
            thumbnail: instance.thumbnail,
            description: instance.description,
            controls: instance.controls,
            category: instance.category || 'Other',
            GameClass: MinigameClass
        });
        console.log(`[MinigameManager] Registered: ${instance.name}`);
    }

    /** Returns the display name of the next minigame (for Set Order), or '?' otherwise. */
    getNextMinigameName() {
        const config = this.gameManager.config;
        if (config.selectedMinigames.length === 0) return null;
        if (config.minigameMode === MinigameMode.SET_ORDER) {
            const idx = this.gameManager.minigameState.currentIndex % config.selectedMinigames.length;
            const gameId = config.selectedMinigames[idx];
            const entry = this._registry.get(gameId);
            return entry ? entry.name : '?';
        }
        return '?';
    }

    /** Returns array of { id, name, thumbnail, category } for the setup wizard. */
    getRegistryList() {
        return [...this._registry.values()].map(r => ({
            id: r.id,
            name: r.name,
            thumbnail: r.thumbnail,
            category: r.category
        }));
    }

    // ── Capture flow ─────────────────────────────────────

    _onCapture(ctx) {
        this._captureCtx = ctx;
        const config = this.gameManager.config;
        const mode = config.minigameMode;
        const selected = config.selectedMinigames;

        if (mode === MinigameMode.ATTACKER_CHOICE || mode === MinigameMode.DEFENDER_CHOICE) {
            // Show chooser popup
            const chooserPlayer = mode === MinigameMode.ATTACKER_CHOICE
                ? (ctx.attackerColor === 'w' ? config.players[0] : config.players[1])
                : (ctx.attackerColor === 'w' ? config.players[1] : config.players[0]);

            const games = selected.map(id => this._registry.get(id)).filter(Boolean);
            this.eventBus.emit('minigameChoose', {
                playerName: chooserPlayer.name,
                games,
                onChoice: (gameId) => this._startMinigame(gameId)
            });
        } else if (mode === MinigameMode.SET_ORDER) {
            const mgState = this.gameManager.minigameState;
            const gameId = selected[mgState.currentIndex % selected.length];
            mgState.currentIndex++;
            this._startMinigame(gameId);
        } else {
            // Random
            const gameId = selected[Math.floor(Math.random() * selected.length)];
            this._startMinigame(gameId);
        }
    }

    _startMinigame(gameId) {
        const entry = this._registry.get(gameId);
        if (!entry) {
            console.error(`[MinigameManager] Unknown minigame: ${gameId}`);
            this.eventBus.emit(GameEvent.MINIGAME_END, { attackerWins: false });
            return;
        }

        const config = this.gameManager.config;
        const mgState = this.gameManager.minigameState;
        const isFirstTime = !mgState.firstTimePlayed.has(gameId);

        // Show the minigame screen (explanation → play → result)
        this.eventBus.emit(GameEvent.MINIGAME_START, {
            gameEntry: entry,
            captureCtx: this._captureCtx,
            players: config.players,
            attackerColor: this._captureCtx.attackerColor,
            advantage: config.minigameAdvantage || 'attacker',
            isFirstTime,
            onReady: () => {
                mgState.firstTimePlayed.add(gameId);
            },
            onEnd: (result) => this._onGameEnd(result, gameId)
        });
    }

    _onGameEnd(result, gameId) {
        if (result.tie) {
            // Tie → replay same minigame
            this.eventBus.emit('minigameTie', {
                onReplay: () => this._startMinigame(gameId)
            });
            return;
        }

        // Clean up and resolve
        this._activeGame = null;
        this._captureCtx = null;
        this.eventBus.emit(GameEvent.MINIGAME_END, {
            attackerWins: result.attackerWins
        });
    }
}
