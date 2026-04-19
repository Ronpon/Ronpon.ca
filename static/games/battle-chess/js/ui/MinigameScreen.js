import { GameEvent } from '../Constants.js';

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
    }

    _show({ gameEntry, captureCtx, players, attackerColor, advantage, isFirstTime, onReady, onEnd }) {
        this._currentCtx = { gameEntry, players, attackerColor, advantage, onEnd };

        const p1 = players[0];
        const p2 = players[1];
        const p1Role = attackerColor === 'w' ? 'Attacker' : 'Defender';
        const p2Role = attackerColor === 'b' ? 'Attacker' : 'Defender';

        // Determine which player has the advantage
        const p1HasAdv = (advantage === 'attacker' && p1Role === 'Attacker') ||
                         (advantage === 'defender' && p1Role === 'Defender');
        const p2HasAdv = (advantage === 'attacker' && p2Role === 'Attacker') ||
                         (advantage === 'defender' && p2Role === 'Defender');
        const advBadge = '<div class="mg-advantage-badge">★ Advantage</div>';

        const panel = document.createElement('div');
        panel.className = 'mg-screen';
        panel.innerHTML = `
            <div class="mg-sidebar mg-sidebar-left">
                <div class="mg-player-icon">${p1.icon || '⚔️'}</div>
                <div class="mg-player-name">${this._escapeHtml(p1.name)}</div>
                <div class="mg-player-role mg-role-${p1Role.toLowerCase()}">${p1Role}</div>
                ${p1HasAdv ? advBadge : ''}
                <div class="mg-controls-hint">${this._escapeHtml(gameEntry.controls?.player1 || '')}</div>
            </div>
            <div class="mg-center">
                <div class="mg-title">${this._escapeHtml(gameEntry.name)}</div>
                <div class="mg-arena" id="mg-arena"></div>
            </div>
            <div class="mg-sidebar mg-sidebar-right">
                <div class="mg-player-icon">${p2.icon || '🛡️'}</div>
                <div class="mg-player-name">${this._escapeHtml(p2.name)}</div>
                <div class="mg-player-role mg-role-${p2Role.toLowerCase()}">${p2Role}</div>
                ${p2HasAdv ? advBadge : ''}
                <div class="mg-controls-hint">${this._escapeHtml(gameEntry.controls?.player2 || '')}</div>
            </div>
        `;

        this.container.innerHTML = '';
        this.container.appendChild(panel);
        this.container.classList.add('active');

        const arena = panel.querySelector('#mg-arena');

        // Create and init the game instance first to get the dynamic description
        const GameClass = gameEntry.GameClass;
        this._gameInstance = new GameClass();
        this._gameInstance.init(arena, {
            players,
            attackerColor,
            advantage,
            onEnd: (result) => {
                this._destroyGame();
                if (result.tie) {
                    onEnd(result);
                } else {
                    this._showResult(result, players, attackerColor, () => {
                        this._hide();
                        onEnd(result);
                    });
                }
            }
        });

        const dynamicDescription = this._gameInstance.description;

        if (isFirstTime && dynamicDescription) {
            this._showExplanation(arena, dynamicDescription, () => {
                onReady();
                this._gameInstance.start();
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

    _showResult(result, players, attackerColor, onDone) {
        const attacker = attackerColor === 'w' ? players[0] : players[1];
        const defender = attackerColor === 'w' ? players[1] : players[0];
        const winner = result.attackerWins ? attacker : defender;
        const winLabel = result.attackerWins ? 'Attacker Wins!' : 'Defender Wins!';

        const overlay = document.createElement('div');
        overlay.className = 'mg-result-overlay';
        overlay.innerHTML = `
            <div class="mg-result-panel">
                <div class="mg-result-icon">${winner.icon || '🏆'}</div>
                <h3 class="mg-result-title">${winLabel}</h3>
                <p class="mg-result-name">${this._escapeHtml(winner.name)}</p>
                <button class="btn btn-primary mg-continue-btn">Continue</button>
            </div>
        `;

        const arena = this.container.querySelector('#mg-arena');
        arena.appendChild(overlay);

        overlay.querySelector('.mg-continue-btn').addEventListener('click', () => {
            onDone();
        });
    }

    _showTie({ onReplay }) {
        // Keep the screen visible, show tie overlay in the arena
        const arena = this.container.querySelector('#mg-arena');
        if (!arena) return;

        this._destroyGame();

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
        this.container.classList.remove('active');
        this.container.innerHTML = '';
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
