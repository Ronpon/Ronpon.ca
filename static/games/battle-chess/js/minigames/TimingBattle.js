import { BaseMinigame } from './BaseMinigame.js';

/**
 * Timing Battle — reaction-time tug-of-war minigame.
 *
 * Same bar & notch layout as Mashing Battle. Player 1 left, Player 2 right.
 * Icon starts 1 notch closer to the attacker's side.
 * "NOW!" appears at random intervals (2–6s). Players race to press their key.
 * Faster player gains 1 notch. Pressing early loses 1 notch (penalty).
 * First to push the icon to the opponent's end wins.
 */
export class TimingBattle extends BaseMinigame {
    constructor() {
        super();
        this.id = 'timing-battle';
        this.name = 'Timing Battle';
        this.thumbnail = '⏱️';
        this.category = 'Skill';
        this.description = 'Wait for "NOW!" then press your key as fast as you can! Fastest reaction wins the round. Press too early and you lose a point. First to push the icon to the far side wins.';
        this.controls = {
            player1: 'Press A on "NOW!"',
            player2: 'Press L on "NOW!"'
        };
    }

    init(container, config) {
        super.init(container, config);

        this.NOTCH_COUNT = 9; // 0–8
        // Determine starting position based on advantage setting
        // 0 = P1 side (left), 8 = P2 side (right), 4 = center
        const p1IsAttacker = this.attackerColor === 'w';
        if (this.advantage === 'none') {
            this.position = 4; // center — no advantage
        } else {
            // 'attacker': start closer to attacker; 'defender': start closer to defender
            const advantagedIsAttacker = this.advantage === 'attacker';
            // If the advantaged side is the attacker, start 1 notch closer to attacker
            // "closer to attacker" means the icon is nearer the attacker's goal line,
            // so the attacker needs fewer wins to push it across
            if (p1IsAttacker === advantagedIsAttacker) {
                this.position = 3; // closer to P1 (left) side
            } else {
                this.position = 5; // closer to P2 (right) side
            }
        }

        // Update description based on advantage
        if (this.advantage === 'attacker') {
            this.description = 'Wait for "NOW!" then press your key as fast as you can! Fastest reaction wins the round. Press too early and you lose a point. First to push the icon to the far side wins. The attacker starts with a slight lead.';
        } else if (this.advantage === 'defender') {
            this.description = 'Wait for "NOW!" then press your key as fast as you can! Fastest reaction wins the round. Press too early and you lose a point. First to push the icon to the far side wins. The defender starts with a slight lead.';
        } else {
            this.description = 'Wait for "NOW!" then press your key as fast as you can! Fastest reaction wins the round. Press too early and you lose a point. First to push the icon to the far side wins. No starting advantage — icon begins at the center.';
        }

        // Round state
        this.phase = 'waiting'; // 'waiting' | 'ready' | 'judging' | 'result' | 'done'
        this.nowTime = 0;       // timestamp when NOW! appeared
        this.p1Time = null;     // reaction time in ms (null = hasn't pressed)
        this.p2Time = null;
        this.p1Early = false;
        this.p2Early = false;

        // Display
        this.roundMessage = '';
        this.displayP1Ms = '';
        this.displayP2Ms = '';

        // Canvas
        this.canvas = null;
        this.ctx = null;
        this.arenaW = 500;
        this.arenaH = 320;

        this._onKeyDown = this._onKeyDown.bind(this);
        this._nowTimeout = null;
        this._roundTimeout = null;
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

        this._draw();
        this._startRound();
    }

    destroy() {
        document.removeEventListener('keydown', this._onKeyDown);
        if (this._nowTimeout) clearTimeout(this._nowTimeout);
        if (this._roundTimeout) clearTimeout(this._roundTimeout);
        super.destroy();
    }

    // ── Round Logic ──────────────────────────────────────

    _startRound() {
        if (this._destroyed) return;

        this.phase = 'waiting';
        this.p1Time = null;
        this.p2Time = null;
        this.p1Early = false;
        this.p2Early = false;
        this.roundMessage = 'Wait for it...';
        this.displayP1Ms = '';
        this.displayP2Ms = '';
        this._draw();

        // Random delay 2–6 seconds before NOW!
        const delay = 2000 + Math.random() * 4000;
        this._nowTimeout = setTimeout(() => {
            if (this._destroyed) return;
            this.phase = 'ready';
            this.nowTime = performance.now();
            this.roundMessage = 'NOW!';
            this._draw();

            // Auto-judge after 2 seconds if nobody pressed
            this._roundTimeout = setTimeout(() => {
                if (this._destroyed) return;
                if (this.phase === 'ready') {
                    this._judgeRound();
                }
            }, 2000);
        }, delay);
    }

    _judgeRound() {
        if (this._destroyed) return;
        this.phase = 'judging';

        // P1 is always left, P2 is always right
        // positive move = toward P2 (right), negative = toward P1 (left)
        let moved = 0;

        if (this.p1Early && this.p2Early) {
            this.roundMessage = 'Both too early!';
        } else if (this.p1Early) {
            // P1 pressed early → penalty, icon moves toward P1 (left)
            moved = -1;
            this.roundMessage = `${this.players[0].name} pressed too early!`;
        } else if (this.p2Early) {
            // P2 pressed early → penalty, icon moves toward P2 (right)
            moved = 1;
            this.roundMessage = `${this.players[1].name} pressed too early!`;
        } else if (this.p1Time !== null && this.p2Time !== null) {
            if (this.p1Time < this.p2Time) {
                moved = 1; // P1 faster → push toward P2
                this.roundMessage = `${this.players[0].name} was faster!`;
            } else if (this.p2Time < this.p1Time) {
                moved = -1; // P2 faster → push toward P1
                this.roundMessage = `${this.players[1].name} was faster!`;
            } else {
                this.roundMessage = 'Perfect tie!';
            }
        } else if (this.p1Time !== null) {
            moved = 1;
            this.roundMessage = `Only ${this.players[0].name} reacted!`;
        } else if (this.p2Time !== null) {
            moved = -1;
            this.roundMessage = `Only ${this.players[1].name} reacted!`;
        } else {
            this.roundMessage = 'Nobody reacted!';
        }

        this.position = Math.max(0, Math.min(this.NOTCH_COUNT - 1, this.position + moved));
        this.phase = 'result';
        this._draw();

        // Check for win
        // 0 = P1's end, NOTCH_COUNT-1 = P2's end
        const p1IsAttacker = this.attackerColor === 'w';
        if (this.position === 0) {
            // Icon at P1's end → P2 wins
            const attackerWins = !p1IsAttacker; // P2 is attacker if !p1IsAttacker
            this._roundTimeout = setTimeout(() => {
                if (!this._destroyed) this.end({ attackerWins, tie: false });
            }, 1200);
            return;
        } else if (this.position === this.NOTCH_COUNT - 1) {
            // Icon at P2's end → P1 wins
            const attackerWins = p1IsAttacker;
            this._roundTimeout = setTimeout(() => {
                if (!this._destroyed) this.end({ attackerWins, tie: false });
            }, 1200);
            return;
        }

        // Next round after a pause
        this._roundTimeout = setTimeout(() => this._startRound(), 1800);
    }

    // ── Input ────────────────────────────────────────────

    _onKeyDown(e) {
        const key = e.key.toLowerCase();
        if (key !== 'a' && key !== 'l') return;
        if (this.phase === 'judging' || this.phase === 'result' || this.phase === 'done') return;

        const isP1 = key === 'a';
        const isP2 = key === 'l';

        if (this.phase === 'waiting') {
            // Pressed too early!
            if (isP1 && this.p1Time === null && !this.p1Early) {
                this.p1Early = true;
                this.displayP1Ms = 'EARLY!';
                // If P2 also early or hasn't gone yet, check if we should judge
                if (this.p2Early || this.p2Time !== null) {
                    clearTimeout(this._nowTimeout);
                    this._judgeRound();
                }
                this._draw();
            } else if (isP2 && this.p2Time === null && !this.p2Early) {
                this.p2Early = true;
                this.displayP2Ms = 'EARLY!';
                if (this.p1Early || this.p1Time !== null) {
                    clearTimeout(this._nowTimeout);
                    this._judgeRound();
                }
                this._draw();
            }
        } else if (this.phase === 'ready') {
            // Reacting to NOW!
            const reaction = performance.now() - this.nowTime;
            if (isP1 && this.p1Time === null) {
                this.p1Time = Math.round(reaction);
                this.displayP1Ms = this.p1Time + 'ms';
                this._draw();
            } else if (isP2 && this.p2Time === null) {
                this.p2Time = Math.round(reaction);
                this.displayP2Ms = this.p2Time + 'ms';
                this._draw();
            }

            // If both have responded, judge immediately
            if ((this.p1Time !== null || this.p1Early) && (this.p2Time !== null || this.p2Early)) {
                clearTimeout(this._roundTimeout);
                setTimeout(() => this._judgeRound(), 400);
            }
        }
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
        const barY = H * 0.45;
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

        // ── Moving icon ──
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
        const p1IsAtt = this.attackerColor === 'w';
        ctx.font = 'bold 12px "Segoe UI", sans-serif';
        ctx.fillStyle = p1IsAtt ? '#e94560' : '#4ecdc4';
        ctx.textAlign = 'left';
        ctx.fillText(p1IsAtt ? 'Attacker' : 'Defender', barLeft, barY + 36);
        ctx.fillStyle = p1IsAtt ? '#4ecdc4' : '#e94560';
        ctx.textAlign = 'right';
        ctx.fillText(p1IsAtt ? 'Defender' : 'Attacker', barRight, barY + 36);

        // ── Player names ──
        ctx.font = '11px "Segoe UI", sans-serif';
        ctx.fillStyle = '#888';
        ctx.textAlign = 'center';
        ctx.fillText(p1.name, 28, barY + 28);
        ctx.fillText(p2.name, W - 28, barY + 28);

        // ── Reaction times — P1 on left, P2 on right ──
        ctx.font = 'bold 14px "Segoe UI", sans-serif';
        if (this.displayP1Ms) {
            ctx.fillStyle = this.displayP1Ms === 'EARLY!' ? '#e94560' : '#4ecdc4';
            ctx.textAlign = 'center';
            ctx.fillText(this.displayP1Ms, 28, barY + 44);
        }
        if (this.displayP2Ms) {
            ctx.fillStyle = this.displayP2Ms === 'EARLY!' ? '#e94560' : '#4ecdc4';
            ctx.textAlign = 'center';
            ctx.fillText(this.displayP2Ms, W - 28, barY + 44);
        }

        // ── Central message (NOW! / Wait / Result) ──
        ctx.textAlign = 'center';
        if (this.roundMessage === 'NOW!') {
            ctx.font = 'bold 64px "Segoe UI", sans-serif';
            ctx.fillStyle = '#e94560';
            ctx.fillText('NOW!', W / 2, H * 0.18);
        } else if (this.roundMessage) {
            ctx.font = 'bold 20px "Segoe UI", sans-serif';
            ctx.fillStyle = this.phase === 'result' ? '#e0e0e0' : '#666';
            ctx.fillText(this.roundMessage, W / 2, H * 0.18);
        }

        // ── Win message at bottom ──
        if (this.position === 0 || this.position === this.NOTCH_COUNT - 1) {
            const winner = this.position === 0 ? p2 : p1;
            ctx.font = 'bold 22px "Segoe UI", sans-serif';
            ctx.fillStyle = '#e94560';
            ctx.fillText(`${winner.name} Wins!`, W / 2, H * 0.85);
        }
    }
}
