import { BaseMinigame } from './BaseMinigame.js';

/**
 * Mashing Battle — button-mashing tug-of-war minigame.
 *
 * A bar with 9 notches. Player 1 on left, Player 2 on right.
 * Icon starts 1 notch closer to the attacker's side.
 * 3-2-1-GO countdown, then 20-second timer.
 * Player 1 mashes A, Player 2 mashes L. Every 5 presses moves the icon 1 notch.
 * Whichever side the icon is closest to at the end wins.
 */
export class MashingBattle extends BaseMinigame {
    constructor() {
        super();
        this.id = 'mashing-battle';
        this.name = 'Mashing Battle';
        this.thumbnail = '💪';
        this.category = 'Skill';
        this.description = 'Mash your button as fast as you can! Every 5 presses moves the icon one notch toward your opponent. Closest side after 20 seconds wins.';
        this.controls = {
            player1: 'Mash A',
            player2: 'Mash L'
        };
    }

    init(container, config) {
        super.init(container, config);

        this.NOTCH_COUNT = 9;       // 0–8, center = 4
        this.PRESSES_PER_NOTCH = 5;
        this.DURATION = 20;         // seconds

        // Determine starting position based on advantage setting
        // 0 = P1 side (left), 8 = P2 side (right), 4 = center
        const p1IsAttacker = this.attackerColor === 'w';
        if (this.advantage === 'none') {
            this.position = 4; // center — no advantage
        } else {
            const advantagedIsAttacker = this.advantage === 'attacker';
            if (p1IsAttacker === advantagedIsAttacker) {
                this.position = 3; // closer to P1 (left) side
            } else {
                this.position = 5; // closer to P2 (right) side
            }
        }

        // Update description based on advantage
        if (this.advantage === 'attacker') {
            this.description = 'Mash your button as fast as you can! Every 5 presses moves the icon one notch toward your opponent. Closest side after 20 seconds wins. Attacker starts with a slight advantage.';
        } else if (this.advantage === 'defender') {
            this.description = 'Mash your button as fast as you can! Every 5 presses moves the icon one notch toward your opponent. Closest side after 20 seconds wins. Defender starts with a slight advantage.';
        } else {
            this.description = 'Mash your button as fast as you can! Every 5 presses moves the icon one notch toward your opponent. Closest side after 20 seconds wins. No starting advantage — icon begins at the center.';
        }

        // Press counts (accumulated, resets every 5)
        this.p1Presses = 0;
        this.p2Presses = 0;

        // Timer
        this.timeLeft = this.DURATION;
        this.running = false;
        this.countdownValue = 3;

        // Canvas
        this.canvas = null;
        this.ctx = null;
        this.arenaW = 500;
        this.arenaH = 300;

        this._onKeyDown = this._onKeyDown.bind(this);
    }

    start() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.arenaW;
        this.canvas.height = this.arenaH;
        this.canvas.style.cssText = 'display:block; margin:auto; background:#0a0f1a; border-radius:4px;';
        this.container.innerHTML = '';
        this.container.style.display = 'flex';
        this.container.style.alignItems = 'center';
        this.container.style.justifyContent = 'center';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        document.addEventListener('keydown', this._onKeyDown);

        this._lastTime = performance.now();
        this._startCountdown();
    }

    destroy() {
        document.removeEventListener('keydown', this._onKeyDown);
        if (this._countdownTimer) clearTimeout(this._countdownTimer);
        if (this._gameTimer) clearInterval(this._gameTimer);
        super.destroy();
    }

    // ── Countdown ────────────────────────────────────────

    _startCountdown() {
        this.countdownValue = 3;
        this._draw();
        this._countdownTick();
    }

    _countdownTick() {
        if (this._destroyed) return;
        this._draw();

        if (this.countdownValue > 0) {
            this.countdownValue--;
            this._countdownTimer = setTimeout(() => this._countdownTick(), 1000);
        } else {
            // "GO!" frame — start after a brief moment
            this._countdownTimer = setTimeout(() => {
                this.countdownValue = -1; // signals "running"
                this.running = true;
                this._lastTime = performance.now();
                this._gameTimer = setInterval(() => this._timerTick(), 100);
                this._loop();
            }, 500);
        }
    }

    _timerTick() {
        if (this._destroyed || !this.running) return;
        this.timeLeft -= 0.1;
        if (this.timeLeft <= 0) {
            this.timeLeft = 0;
            this.running = false;
            clearInterval(this._gameTimer);
            this._endGame();
        }
    }

    // ── Game Loop ────────────────────────────────────────

    _loop() {
        if (this._destroyed) return;
        this._draw();
        if (this.running) {
            this.requestFrame(() => this._loop());
        }
    }

    // ── Input ────────────────────────────────────────────

    _onKeyDown(e) {
        if (!this.running) return;
        const key = e.key.toLowerCase();

        // P1 = A → pushes icon right (toward P2)
        // P2 = L → pushes icon left (toward P1)
        if (key === 'a') {
            this.p1Presses++;
            if (this.p1Presses >= this.PRESSES_PER_NOTCH) {
                this.p1Presses = 0;
                this.position = Math.min(this.NOTCH_COUNT - 1, this.position + 1);
            }
        } else if (key === 'l') {
            this.p2Presses++;
            if (this.p2Presses >= this.PRESSES_PER_NOTCH) {
                this.p2Presses = 0;
                this.position = Math.max(0, this.position - 1);
            }
        }
    }

    // ── End ──────────────────────────────────────────────

    _endGame() {
        // Center = 4. < 4 = P1 side, > 4 = P2 side
        const center = Math.floor(this.NOTCH_COUNT / 2); // 4
        const p1IsAttacker = this.attackerColor === 'w';
        this._draw();

        setTimeout(() => {
            if (this._destroyed) return;
            if (this.position === center) {
                this.end({ attackerWins: false, tie: true });
            } else {
                // Icon closer to P1 side (< 4) → P2 wins; closer to P2 side (> 4) → P1 wins
                const p1Wins = this.position > center;
                this.end({ attackerWins: p1IsAttacker ? p1Wins : !p1Wins, tie: false });
            }
        }, 800);
    }

    // ── Drawing ──────────────────────────────────────────

    _draw() {
        const ctx = this.ctx;
        const W = this.arenaW;
        const H = this.arenaH;
        if (!ctx) return;

        ctx.fillStyle = '#0a0f1a';
        ctx.fillRect(0, 0, W, H);

        const p1 = this.players[0];
        const p2 = this.players[1];

        // ── Bar geometry ──
        const barY = H * 0.5;
        const barLeft = 60;
        const barRight = W - 60;
        const barW = barRight - barLeft;
        const notchSpacing = barW / (this.NOTCH_COUNT - 1);

        // ── Player icons on sides ──
        ctx.font = '32px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(p1.icon || '⚔️', 28, barY);
        ctx.fillText(p2.icon || '🛡️', W - 28, barY);

        // ── Bar line ──
        ctx.strokeStyle = '#0f3460';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(barLeft, barY);
        ctx.lineTo(barRight, barY);
        ctx.stroke();

        // ── Notches ──
        for (let i = 0; i < this.NOTCH_COUNT; i++) {
            const x = barLeft + i * notchSpacing;
            const isCenter = i === Math.floor(this.NOTCH_COUNT / 2);
            ctx.strokeStyle = isCenter ? '#e94560' : '#4a6fa5';
            ctx.lineWidth = isCenter ? 3 : 2;
            ctx.beginPath();
            ctx.moveTo(x, barY - 14);
            ctx.lineTo(x, barY + 14);
            ctx.stroke();
        }

        // ── Moving icon (circle with Battle Chess icon) ──
        const iconX = barLeft + this.position * notchSpacing;
        ctx.beginPath();
        ctx.arc(iconX, barY, 18, 0, Math.PI * 2);
        ctx.fillStyle = '#e94560';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.font = '18px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#fff';
        ctx.fillText('♚', iconX, barY + 1);

        // ── Player labels ──
        const p1IsAttacker = this.attackerColor === 'w';
        ctx.font = 'bold 12px "Segoe UI", sans-serif';
        ctx.fillStyle = p1IsAttacker ? '#e94560' : '#4ecdc4';
        ctx.textAlign = 'left';
        ctx.fillText(p1IsAttacker ? 'Attacker' : 'Defender', barLeft, barY + 40);
        ctx.fillStyle = p1IsAttacker ? '#4ecdc4' : '#e94560';
        ctx.textAlign = 'right';
        ctx.fillText(p1IsAttacker ? 'Defender' : 'Attacker', barRight, barY + 40);

        // ── Timer ──
        ctx.font = 'bold 36px "Segoe UI", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#e0e0e0';
        if (this.countdownValue > 0) {
            ctx.fillText(this.countdownValue, W / 2, H * 0.2);
        } else if (this.countdownValue === 0) {
            ctx.fillStyle = '#e94560';
            ctx.fillText('GO!', W / 2, H * 0.2);
        } else {
            // Running / finished
            const display = Math.max(0, this.timeLeft).toFixed(1);
            ctx.fillStyle = this.timeLeft <= 5 ? '#e94560' : '#e0e0e0';
            ctx.fillText(display + 's', W / 2, H * 0.2);
        }

        // ── Press counters (show progress toward next notch) ──
        if (this.running || this.timeLeft <= 0) {
            ctx.font = '13px "Segoe UI", sans-serif';
            ctx.fillStyle = '#666';
            ctx.textAlign = 'left';
            ctx.fillText(`${this.p1Presses}/${this.PRESSES_PER_NOTCH}`, barLeft, barY + 56);
            ctx.textAlign = 'right';
            ctx.fillText(`${this.p2Presses}/${this.PRESSES_PER_NOTCH}`, barRight, barY + 56);
        }

        // ── Player names below icons ──
        ctx.font = '11px "Segoe UI", sans-serif';
        ctx.fillStyle = '#888';
        ctx.textAlign = 'center';
        ctx.fillText(p1.name, 28, barY + 30);
        ctx.fillText(p2.name, W - 28, barY + 30);
    }
}
