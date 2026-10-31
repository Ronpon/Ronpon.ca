import { GameEvent, GameState } from '../Constants.js';
import { createBattleLayout, createBattleResult, captureConsequence } from './BattleLayout.js';

/**
 * Full-screen minigame wrapper UI.
 * Layout: [P1 info + controls] | [minigame area] | [P2 info + controls]
 *
 * Handles:
 *   - First-time explanation overlay ("Got It")
 *   - Minigame container for the game to render into
 *   - Tie overlay ("Here we go again")
 *   - Result announcement
 */
export class MinigameScreen {
    constructor(overlayContainer, eventBus) {
        this.container = overlayContainer;
        this.eventBus = eventBus;
        this._gameInstance = null;
        this._currentCtx = null;

        this.eventBus.on(GameEvent.MINIGAME_START, (ctx) => this._show(ctx));
        this.eventBus.on('minigameTie', (ctx) => this._showTie(ctx));
        this.eventBus.on(GameEvent.STATE_CHANGED, ({ to }) => {
            if (this._currentCtx && (to === GameState.SETUP || to === GameState.GAME_OVER)) {
                this._hide();
            }
        });
    }

    _show({ gameEntry, captureCtx, players, attackerColor, advantage, attackerLosesPiece = false, aiDifficulty = 'medium', isFirstTime, onReady, onEnd }) {
        this._destroyGame();
        this._currentCtx = { gameEntry, players, attackerColor, advantage, aiDifficulty, onEnd };
        const screenCtx = this._currentCtx;

        const panel = createBattleLayout({
            players, attackerColor, advantage, gameEntry,
            controls: players.map((player, index) => player.isAI
                ? `Computer controlled · ${aiDifficulty}`
                : gameEntry.controls?.[index === 0 ? 'player1' : 'player2'])
        });

        this.container.innerHTML = '';
        this.container.appendChild(panel);
        this.container.classList.add('active');

        const arena = panel.querySelector('#mg-arena');

        // Create and init the game instance first to get the dynamic description
        const GameClass = gameEntry.GameClass;
        const game = new GameClass();
        this._gameInstance = game;
        game.init(arena, {
            players,
            attackerColor,
            advantage,
            aiDifficulty,
            onEnd: (result) => {
                if (this._currentCtx !== screenCtx || this._gameInstance !== game) return;
                this._destroyGame();
                if (result.tie) {
                    onEnd(result);
                } else {
                    const consequence = captureConsequence(result.attackerWins, captureCtx?.move?.piece === 'k', attackerLosesPiece);
                    this._showResult(result, players, attackerColor, () => {
                        if (this._currentCtx !== screenCtx) return;
                        this._hide();
                        onEnd(result);
                    }, consequence);
                }
            }
        });

        const dynamicDescription = this._gameInstance.description;

        if (isFirstTime && dynamicDescription) {
            this._showExplanation(arena, dynamicDescription, () => {
                if (this._currentCtx !== screenCtx || this._gameInstance !== game) return;
                onReady();
                game.start();
            });
        } else {
            onReady();
            this._gameInstance.start();
        }
    }

    _showExplanation(arena, description, onGotIt) {
        const overlay = document.createElement('div');
        overlay.className = 'mg-explanation';
        overlay.innerHTML = `
            <p class="mg-explanation-text">${this._escapeHtml(description)}</p>
            <button class="btn btn-primary mg-gotit-btn">Got It</button>
        `;
        arena.appendChild(overlay);

        overlay.querySelector('.mg-gotit-btn').addEventListener('click', () => {
            overlay.remove();
            onGotIt();
        });
    }

    _showResult(result, players, attackerColor, onDone, consequence) {
        const overlay = createBattleResult({ result, players, attackerColor, consequence, onContinue: onDone });
        this.container.querySelector('#mg-arena').appendChild(overlay);
    }

    _showTie({ onReplay }) {
        // Keep the screen visible, show tie overlay in the arena
        const arena = this.container.querySelector('#mg-arena');
        if (!arena) return;

        this._destroyGame();
        const screenCtx = this._currentCtx;

        const overlay = document.createElement('div');
        overlay.className = 'mg-result-overlay';
        overlay.innerHTML = `
            <div class="mg-result-panel">
                <div class="mg-result-icon">😮</div>
                <h3 class="mg-result-title">Whoa… it's a tie!</h3>
                <button class="btn btn-primary mg-replay-btn">Here we go again</button>
            </div>
        `;
        arena.appendChild(overlay);

        overlay.querySelector('.mg-replay-btn').addEventListener('click', () => {
            if (this._currentCtx !== screenCtx) return;
            overlay.remove();
            this._hide();
            onReplay();
        });
    }

    _destroyGame() {
        if (this._gameInstance) {
            this._gameInstance.destroy();
            this._gameInstance = null;
        }
    }

    _hide() {
        this._destroyGame();
        this._currentCtx = null;
        this.container.classList.remove('active');
        this.container.innerHTML = '';
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
