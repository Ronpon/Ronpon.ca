import { EventBus } from './EventBus.js';
import { GameManager } from './GameManager.js';
import { SkinManager } from './SkinManager.js';
import { Board } from './Board.js';
import { InputHandler } from './InputHandler.js';
import { MinigameManager } from './MinigameManager.js';
import { PromotionDialog } from './ui/PromotionDialog.js';
import { GameOverOverlay } from './ui/GameOverOverlay.js';
import { SetupWizard } from './ui/SetupWizard.js';
import { MinigameScreen } from './ui/MinigameScreen.js';
import { MinigameChooser } from './ui/MinigameChooser.js';
import { CheckWarning } from './ui/CheckWarning.js';
import { GameEvent, BOARD_SIZE } from './Constants.js';

// ── Minigame imports (add new minigames here) ──
import { DodgingBattle } from './minigames/DodgingBattle.js';
import { MashingBattle } from './minigames/MashingBattle.js';
import { TimingBattle } from './minigames/TimingBattle.js';
import { HighestCard } from './minigames/HighestCard.js';
import { MemoryMatch } from './minigames/MemoryMatch.js';

/**
 * Application entry point.
 * Wires together all core systems and kicks off the game.
 */
class App {
    constructor() {
        // ── DOM references ──
        this.canvas = document.getElementById('game-canvas');
        this.overlay = document.getElementById('overlay-container');
        this.turnIndicator = document.getElementById('turn-indicator');

        // ── Core systems ──
        this.eventBus = new EventBus();
        this.gameManager = new GameManager(this.eventBus);
        this.skinManager = new SkinManager();
        this.minigameManager = new MinigameManager(this.eventBus, this.gameManager);
        this.board = null;

        // Register minigames (add new ones here)
        this.minigameManager.register(DodgingBattle);
        this.minigameManager.register(MashingBattle);
        this.minigameManager.register(TimingBattle);
        this.minigameManager.register(HighestCard);
        this.minigameManager.register(MemoryMatch);
        this.inputHandler = null;
        this.checkWarning = null;
        this.promotionDialog = null;
        this.gameOverOverlay = null;
        this.setupWizard = null;
        this.minigameScreen = null;
        this.minigameChooser = null;
    }

    async init() {
        this.canvas.width = BOARD_SIZE;
        this.canvas.height = BOARD_SIZE;

        // Load default skin (board colors + piece rendering)
        await this.skinManager.loadSkin('default');

        // Create board renderer (listens to BOARD_UPDATED events)
        this.board = new Board(this.canvas, this.skinManager, this.eventBus);

        // Create input handler (click-to-select, click-to-move)
        this.inputHandler = new InputHandler(this.canvas, this.board, this.gameManager, this.eventBus);

        // Create check warning popup (injected into input handler)
        this.checkWarning = new CheckWarning(this.overlay);
        this.inputHandler.checkWarning = this.checkWarning;

        // Create UI overlays
        this.promotionDialog = new PromotionDialog(this.overlay, this.inputHandler, this.eventBus);
        this.gameOverOverlay = new GameOverOverlay(this.overlay, this.gameManager, this.eventBus);
        this.minigameScreen = new MinigameScreen(this.overlay, this.eventBus);
        this.minigameChooser = new MinigameChooser(this.overlay, this.eventBus);
        this.setupWizard = new SetupWizard(
            this.overlay, this.eventBus, this.minigameManager.getRegistryList()
        );

        this._setupEventListeners();

        // Show setup wizard
        this.setupWizard.show();

        console.log('[Battle Chess] Initialized — setup wizard shown');
    }

    /**
     * Register a minigame class. Call before init() or at any time before setup.
     * @param {typeof BaseMinigame} MinigameClass
     */
    registerMinigame(MinigameClass) {
        this.minigameManager.register(MinigameClass);
    }

    _setupEventListeners() {
        this.eventBus.on(GameEvent.BOARD_UPDATED, (gameState) => {
            this._updateInfoPanel(gameState);
        });

        this.eventBus.on(GameEvent.STATE_CHANGED, ({ to }) => {
            if (to === 'PLAYING' && this.checkWarning) {
                // Reset "don't show again" at game start (not mid-game resume)
            }
        });

        this.eventBus.on(GameEvent.SETUP_COMPLETE, () => {
            if (this.checkWarning) this.checkWarning.reset();
        });

        this.eventBus.on('showSetup', () => {
            this.setupWizard.minigameRegistry = this.minigameManager.getRegistryList();
            this.setupWizard.show();
        });
    }

    _updateInfoPanel(gameState) {
        const player = gameState.turn === 'w'
            ? gameState.config.players[0]
            : gameState.config.players[1];
        const colorName = gameState.turn === 'w' ? 'White' : 'Black';

        let status = `${player.name} (${colorName}) to move`;
        if (gameState.isCheck) {
            status += ' — CHECK!';
        }
        this.turnIndicator.textContent = status;

        // Toggle check highlight on info panel
        const panel = document.getElementById('info-panel');
        panel.classList.toggle('in-check', !!gameState.isCheck);

        // Update "Next Minigame" display
        const nextMgEl = document.getElementById('next-minigame');
        if (nextMgEl) {
            const mgName = this.minigameManager.getNextMinigameName();
            if (mgName) {
                nextMgEl.textContent = `Next Minigame: ${mgName}`;
                nextMgEl.style.display = '';
            } else {
                nextMgEl.style.display = 'none';
            }
        }
    }
}

// ── Bootstrap ──
document.addEventListener('DOMContentLoaded', async () => {
    window.app = new App();
    await window.app.init();
});
