import { BaseMinigame } from './BaseMinigame.js';

/**
 * Simple test minigame for framework verification.
 * Each player has a button; first to click 5 times wins.
 * Will be replaced by real minigames.
 */
export class TestMinigame extends BaseMinigame {
    constructor() {
        super();
        this.id = 'test-clicker';
        this.name = 'Speed Clicker';
        this.thumbnail = '🖱️';
        this.description = 'Click your button as fast as you can! First to 5 clicks wins.';
        this.controls = {
            player1: 'Click the LEFT button',
            player2: 'Click the RIGHT button'
        };
    }

    init(container, config) {
        super.init(container, config);
        this._scores = [0, 0];
        this._target = 5;
    }

    start() {
        const p1 = this.players[0];
        const p2 = this.players[1];

        this.container.innerHTML = `
            <div style="display:flex; height:100%; align-items:center; justify-content:center; gap:40px; padding:20px;">
                <div style="text-align:center;">
                    <div style="font-size:24px; margin-bottom:10px;">${p1.icon || '⚔️'}</div>
                    <button id="mg-btn-p1" style="font-size:20px; padding:20px 40px; cursor:pointer;
                        background:#0f3460; color:#e0e0e0; border:2px solid #e94560; border-radius:8px;">
                        0 / ${this._target}
                    </button>
                </div>
                <div style="font-size:32px; color:#e94560; font-weight:bold;">VS</div>
                <div style="text-align:center;">
                    <div style="font-size:24px; margin-bottom:10px;">${p2.icon || '🛡️'}</div>
                    <button id="mg-btn-p2" style="font-size:20px; padding:20px 40px; cursor:pointer;
                        background:#0f3460; color:#e0e0e0; border:2px solid #4ecdc4; border-radius:8px;">
                        0 / ${this._target}
                    </button>
                </div>
            </div>
        `;

        const btn1 = this.container.querySelector('#mg-btn-p1');
        const btn2 = this.container.querySelector('#mg-btn-p2');

        btn1.addEventListener('click', () => {
            if (this._destroyed) return;
            this._scores[0]++;
            btn1.textContent = `${this._scores[0]} / ${this._target}`;
            if (this._scores[0] >= this._target) {
                // Player 1 won — is that the attacker?
                const attackerWins = this.attackerColor === 'w';
                this.end({ attackerWins, tie: false });
            }
        });

        btn2.addEventListener('click', () => {
            if (this._destroyed) return;
            this._scores[1]++;
            btn2.textContent = `${this._scores[1]} / ${this._target}`;
            if (this._scores[1] >= this._target) {
                const attackerWins = this.attackerColor === 'b';
                this.end({ attackerWins, tie: false });
            }
        });
    }
}
