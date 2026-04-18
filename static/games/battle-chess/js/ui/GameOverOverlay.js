import { GameEvent } from '../Constants.js';

/**
 * Shows the game-over overlay with result and replay options.
 */
export class GameOverOverlay {
    constructor(overlayContainer, gameManager, eventBus) {
        this.container = overlayContainer;
        this.gameManager = gameManager;
        this.eventBus = eventBus;
        this.panel = null;

        this.eventBus.on(GameEvent.GAME_OVER, (state) => this.show(state));
    }

    show(gameState) {
        const result = this._getResultText(gameState);

        this.panel = document.createElement('div');
        this.panel.className = 'overlay-panel';
        this.panel.innerHTML = `
            <h2>Game Over</h2>
            <p class="game-over-result">${result}</p>
            <div class="game-over-actions">
                <button class="btn btn-primary" id="play-again-btn">Play Again</button>
                <button class="btn" id="new-game-btn">New Game</button>
            </div>
        `;

        this.panel.querySelector('#play-again-btn').addEventListener('click', () => {
            this.hide();
            this.gameManager.startGame();
        });

        this.panel.querySelector('#new-game-btn').addEventListener('click', () => {
            this.hide();
            this.gameManager.reset();
            // SetupWizard listens for state change to SETUP
            this.eventBus.emit('showSetup');
        });

        this.container.innerHTML = '';
        this.container.appendChild(this.panel);
        this.container.classList.add('active');
    }

    hide() {
        this.container.classList.remove('active');
        this.container.innerHTML = '';
        this.panel = null;
    }

    _getResultText(gameState) {
        if (gameState.isCheckmate) {
            // forcedCheckmate: the attacker lost the minigame while in check
            // Regular checkmate: chess.js detected it (turn = side that's mated)
            const loser = gameState.turn === 'w'
                ? gameState.config.players[0].name
                : gameState.config.players[1].name;
            const winner = gameState.turn === 'w'
                ? gameState.config.players[1].name
                : gameState.config.players[0].name;
            if (gameState.forcedCheckmate) {
                return `${loser} failed the minigame while in check — <strong>${winner}</strong> wins!`;
            }
            return `Checkmate! <strong>${winner}</strong> wins!`;
        }
        if (gameState.isStalemate) {
            return 'Stalemate — it\'s a draw!';
        }
        if (gameState.isDraw) {
            return 'Draw!';
        }
        return 'Game over!';
    }
}
