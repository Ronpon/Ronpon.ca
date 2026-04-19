import { BaseMinigame } from './BaseMinigame.js';

/**
 * Dodging Battle — the first real Battle Chess minigame.
 *
 * Both players dodge projectiles in a square arena.
 * Attacker gets an extra life (second chance).
 * Projectiles increase in speed and frequency over time.
 *
 * Controls: P1 = WASD, P2 = IJKL (fixed per player, not per role).
 */
export class DodgingBattle extends BaseMinigame {
    constructor() {
        super();
        this.id = 'dodging-battle';
        this.name = 'Dodging Battle';
        this.thumbnail = '💥';
        this.category = 'Skill';
        this.description = 'Dodge the incoming projectiles! Last player standing wins.';
        this.controls = {
            player1: 'WASD to move',
            player2: 'IJKL to move'
        };
    }

    init(container, config) {
        super.init(container, config);

        // Update description based on advantage
        if (this.advantage === 'attacker') {
            this.description = 'Dodge the incoming projectiles! Last player standing wins. The attacker gets one extra life.';
        } else if (this.advantage === 'defender') {
            this.description = 'Dodge the incoming projectiles! Last player standing wins. The defender gets one extra life.';
        } else {
            this.description = 'Dodge the incoming projectiles! Last player standing wins. No extra lives — one hit and you\'re out!';
        }

        // ── Arena dimensions ─────────────────────────────
        this.arenaSize = 400;
        this.playerRadius = 16;
        this.projectileRadius = 5;

        // ── Player state ─────────────────────────────────
        // Determine extra life based on advantage setting
        const p1IsAttacker = this.attackerColor === 'w';
        let p1Lives = 1, p2Lives = 1;
        if (this.advantage === 'attacker') {
            p1Lives = p1IsAttacker ? 2 : 1;
            p2Lives = p1IsAttacker ? 1 : 2;
        } else if (this.advantage === 'defender') {
            p1Lives = p1IsAttacker ? 1 : 2;
            p2Lives = p1IsAttacker ? 2 : 1;
        }
        // 'none' → both get 1 life

        this.p1 = {
            x: this.arenaSize * 0.3,
            y: this.arenaSize * 0.5,
            lives: p1Lives,
            alive: true,
            icon: this.players[0].icon || '⚔️'
        };
        this.p2 = {
            x: this.arenaSize * 0.7,
            y: this.arenaSize * 0.5,
            lives: p2Lives,
            alive: true,
            icon: this.players[1].icon || '🛡️'
        };

        // ── Projectiles ──────────────────────────────────
        this.projectiles = [];
        this.speed = 120;           // px/s base projectile speed
        this.spawnInterval = 1.2;   // seconds between spawns (decreases)
        this.spawnTimer = 0;
        this.elapsed = 0;

        // ── Input ────────────────────────────────────────
        this.keys = {};
        this.playerSpeed = 180; // px/s

        // ── Pause state (for attacker extra life) ────────
        this.paused = false;
        this.pauseOverlay = null;
        this.countdownValue = 0;

        // ── Canvas ───────────────────────────────────────
        this.canvas = null;
        this.ctx = null;

        this._onKeyDown = this._onKeyDown.bind(this);
        this._onKeyUp = this._onKeyUp.bind(this);
    }

    start() {
        // Create canvas filling the arena container
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.arenaSize;
        this.canvas.height = this.arenaSize;
        this.canvas.style.cssText = 'display:block; margin:auto; background:#0a0f1a; border-radius:4px;';
        this.container.innerHTML = '';
        this.container.style.display = 'flex';
        this.container.style.alignItems = 'center';
        this.container.style.justifyContent = 'center';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        // Key listeners
        document.addEventListener('keydown', this._onKeyDown);
        document.addEventListener('keyup', this._onKeyUp);

        this._lastTime = performance.now();
        this._loop();
    }

    destroy() {
        document.removeEventListener('keydown', this._onKeyDown);
        document.removeEventListener('keyup', this._onKeyUp);
        this.paused = false;
        if (this.pauseOverlay && this.pauseOverlay.parentNode) {
            this.pauseOverlay.remove();
        }
        super.destroy();
    }

    // ── Game Loop ────────────────────────────────────────

    _loop() {
        if (this._destroyed) return;
        const now = performance.now();
        const dt = Math.min((now - this._lastTime) / 1000, 0.05); // cap at 50ms
        this._lastTime = now;

        if (!this.paused) {
            this._update(dt);
        }
        this._draw();
        this.requestFrame(() => this._loop());
    }

    _update(dt) {
        this.elapsed += dt;

        // ── Move players ─────────────────────────────────
        this._movePlayer(this.p1, 'w', 's', 'a', 'd', dt);
        this._movePlayer(this.p2, 'i', 'k', 'j', 'l', dt);

        // ── Spawn projectiles (grace period: first 1.5s no spawns) ──
        if (this.elapsed > 1.5) {
            this.spawnTimer += dt;
            const currentInterval = Math.max(0.15, this.spawnInterval - (this.elapsed - 1.5) * 0.04);
            if (this.spawnTimer >= currentInterval) {
                this.spawnTimer = 0;
                this._spawnProjectile();
            }
        }

        // ── Move projectiles ─────────────────────────────
        const currentSpeed = this.speed + this.elapsed * 12;
        for (const p of this.projectiles) {
            p.x += p.vx * dt * (currentSpeed / this.speed);
            p.y += p.vy * dt * (currentSpeed / this.speed);
        }

        // ── Remove off-screen projectiles ────────────────
        const margin = 20;
        this.projectiles = this.projectiles.filter(p =>
            p.x > -margin && p.x < this.arenaSize + margin &&
            p.y > -margin && p.y < this.arenaSize + margin
        );

        // ── Collision detection ──────────────────────────
        let p1Hit = false, p2Hit = false;

        if (this.p1.alive) {
            for (const proj of this.projectiles) {
                if (this._circlesCollide(this.p1.x, this.p1.y, this.playerRadius, proj.x, proj.y, this.projectileRadius)) {
                    p1Hit = true;
                    break;
                }
            }
        }
        if (this.p2.alive) {
            for (const proj of this.projectiles) {
                if (this._circlesCollide(this.p2.x, this.p2.y, this.playerRadius, proj.x, proj.y, this.projectileRadius)) {
                    p2Hit = true;
                    break;
                }
            }
        }

        // ── Handle hits ──────────────────────────────────
        if (p1Hit && p2Hit) {
            // Both hit same frame
            this.p1.lives--;
            this.p2.lives--;
            if (this.p1.lives <= 0 && this.p2.lives <= 0) {
                this.p1.alive = false;
                this.p2.alive = false;
                this.end({ attackerWins: false, tie: true });
                return;
            }
            // If one still has lives, clear projectiles and pause for them
            if (this.p1.lives > 0) {
                this._triggerExtraLife(this.p1, 0);
                if (this.p2.lives <= 0) this.p2.alive = false;
            } else if (this.p2.lives > 0) {
                this._triggerExtraLife(this.p2, 1);
                if (this.p1.lives <= 0) this.p1.alive = false;
            }
        } else if (p1Hit) {
            this.p1.lives--;
            if (this.p1.lives <= 0) {
                this.p1.alive = false;
                // P1 eliminated → P2 (player index 1) wins
                const attackerWins = this.attackerColor === 'b'; // P2 won
                this.end({ attackerWins, tie: false });
                return;
            }
            this._triggerExtraLife(this.p1, 0);
        } else if (p2Hit) {
            this.p2.lives--;
            if (this.p2.lives <= 0) {
                this.p2.alive = false;
                // P2 eliminated → P1 (player index 0) wins
                const attackerWins = this.attackerColor === 'w'; // P1 won
                this.end({ attackerWins, tie: false });
                return;
            }
            this._triggerExtraLife(this.p2, 1);
        }
    }

    // ── Extra Life Pause ─────────────────────────────────

    _triggerExtraLife(player, playerIndex) {
        this.projectiles = [];
        this.paused = true;

        const roleName = (playerIndex === 0 && this.attackerColor === 'w') ||
                         (playerIndex === 1 && this.attackerColor === 'b')
                         ? 'Attacker' : 'Defender';

        this.pauseOverlay = document.createElement('div');
        this.pauseOverlay.className = 'mg-explanation';
        this.pauseOverlay.innerHTML = `
            <p class="mg-explanation-text" style="font-size:20px; font-weight:bold;">
                ${roleName} has ${player.lives} life remaining
            </p>
            <p class="mg-countdown" style="font-size:64px; font-weight:bold; color:#e94560;">5</p>
        `;
        this.container.appendChild(this.pauseOverlay);

        this.countdownValue = 5;
        this._countdownTick(player);
    }

    _countdownTick(player) {
        if (this._destroyed) return;
        if (this.countdownValue <= 0) {
            if (this.pauseOverlay && this.pauseOverlay.parentNode) {
                this.pauseOverlay.remove();
            }
            this.pauseOverlay = null;
            this.paused = false;
            this._lastTime = performance.now();
            return;
        }

        const el = this.pauseOverlay?.querySelector('.mg-countdown');
        if (el) el.textContent = this.countdownValue;
        this.countdownValue--;
        setTimeout(() => this._countdownTick(player), 1000);
    }

    // ── Player Movement ──────────────────────────────────

    _movePlayer(player, upKey, downKey, leftKey, rightKey, dt) {
        if (!player.alive) return;
        let dx = 0, dy = 0;
        if (this.keys[upKey]) dy -= 1;
        if (this.keys[downKey]) dy += 1;
        if (this.keys[leftKey]) dx -= 1;
        if (this.keys[rightKey]) dx += 1;

        // Normalize diagonal
        if (dx !== 0 && dy !== 0) {
            const len = Math.sqrt(dx * dx + dy * dy);
            dx /= len;
            dy /= len;
        }

        player.x += dx * this.playerSpeed * dt;
        player.y += dy * this.playerSpeed * dt;

        // Clamp to arena
        const r = this.playerRadius;
        player.x = Math.max(r, Math.min(this.arenaSize - r, player.x));
        player.y = Math.max(r, Math.min(this.arenaSize - r, player.y));
    }

    // ── Projectile Spawning ──────────────────────────────

    _spawnProjectile() {
        const size = this.arenaSize;
        const edge = Math.floor(Math.random() * 4); // 0=top, 1=right, 2=bottom, 3=left
        let x, y, vx, vy;
        const baseSpeed = this.speed;

        // Random position along the chosen edge
        const pos = Math.random() * size;

        // Aim towards a random point in the inner arena area
        const targetX = size * 0.2 + Math.random() * size * 0.6;
        const targetY = size * 0.2 + Math.random() * size * 0.6;

        switch (edge) {
            case 0: x = pos; y = -10; break;          // top
            case 1: x = size + 10; y = pos; break;    // right
            case 2: x = pos; y = size + 10; break;    // bottom
            case 3: x = -10; y = pos; break;          // left
        }

        const angle = Math.atan2(targetY - y, targetX - x);
        vx = Math.cos(angle) * baseSpeed;
        vy = Math.sin(angle) * baseSpeed;

        this.projectiles.push({ x, y, vx, vy });
    }

    // ── Drawing ──────────────────────────────────────────

    _draw() {
        const ctx = this.ctx;
        const size = this.arenaSize;
        if (!ctx) return;

        // Clear
        ctx.fillStyle = '#0a0f1a';
        ctx.fillRect(0, 0, size, size);

        // Arena border
        ctx.strokeStyle = '#0f3460';
        ctx.lineWidth = 2;
        ctx.strokeRect(1, 1, size - 2, size - 2);

        // Grid lines (subtle)
        ctx.strokeStyle = 'rgba(15, 52, 96, 0.3)';
        ctx.lineWidth = 1;
        for (let i = 1; i < 8; i++) {
            const p = (size / 8) * i;
            ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, size); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(size, p); ctx.stroke();
        }

        // Projectiles
        ctx.fillStyle = '#ff6b6b';
        ctx.shadowColor = '#ff6b6b';
        ctx.shadowBlur = 6;
        for (const p of this.projectiles) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, this.projectileRadius, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.shadowBlur = 0;

        // Players
        if (this.p1.alive) this._drawPlayer(ctx, this.p1, '#4ecdc4', this.attackerColor === 'w');
        if (this.p2.alive) this._drawPlayer(ctx, this.p2, '#e94560', this.attackerColor === 'b');
    }

    _drawPlayer(ctx, player, color, isAttacker) {
        const r = this.playerRadius;

        // Outer glow
        ctx.shadowColor = color;
        ctx.shadowBlur = 10;

        // Circle
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(player.x, player.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        // Inner circle (darker)
        ctx.fillStyle = 'rgba(0,0,0,0.3)';
        ctx.beginPath();
        ctx.arc(player.x, player.y, r - 3, 0, Math.PI * 2);
        ctx.fill();

        // Player icon
        ctx.font = `${r}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(player.icon, player.x, player.y + 1);

        // Lives indicator (small dots above player)
        if (player.lives > 1) {
            for (let i = 0; i < player.lives; i++) {
                ctx.fillStyle = '#fff';
                ctx.beginPath();
                const dotX = player.x - ((player.lives - 1) * 5) / 2 + i * 5;
                ctx.arc(dotX, player.y - r - 6, 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    // ── Collision ────────────────────────────────────────

    _circlesCollide(x1, y1, r1, x2, y2, r2) {
        const dx = x1 - x2;
        const dy = y1 - y2;
        const dist = dx * dx + dy * dy;
        const radii = r1 + r2;
        return dist < radii * radii;
    }

    // ── Input ────────────────────────────────────────────

    _onKeyDown(e) {
        this.keys[e.key.toLowerCase()] = true;
    }

    _onKeyUp(e) {
        this.keys[e.key.toLowerCase()] = false;
    }
}
