export const ONLINE_GAMES = {
    'highest-card': 'Highest Card', 'memory-match': 'Memory Match',
    'mashing-battle': 'Mashing Battle', 'timing-battle': 'Timing Battle',
    'dodging-battle': 'Dodging Battle'
};
const LIVE = ['mashing-battle', 'timing-battle', 'dodging-battle'];
const cardText = value => ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'][value % 13]
    + ['♠', '♥', '♦', '♣'][Math.floor(value / 13)];

/** Persistent battle view: incoming frames never replace held controls. */
export class OnlineBattleScreen {
    constructor(online) {
        this.online = online;
        this.id = null;
        this.sending = false;
        this.pending = null;
        this.keys = new Set();
        this.taps = 0;
        this.press = null;
        this._down = event => this._key(event, true);
        this._up = event => this._key(event, false);
        this._blur = () => { this.keys.clear(); this.taps = 0; this.press = null; };
    }

    get live() { return !!(this.id && LIVE.includes(this.room.battle.gameId) && this.room.battle.outcome === null); }
    now() { return this.room._serverAt + (performance.now() - this.room._receivedAt) / 1000; }

    update(room) {
        if (this.id !== room.battle.id) {
            this.destroy();
            this.id = room.battle.id;
            this.online._panel(ONLINE_GAMES[room.battle.gameId] || 'Choose a Minigame', `
                <p id="online-battle-context"></p><p id="online-battle-help"></p>
                <p id="online-battle-status" role="status"></p><div id="online-battle-play"></div>
                <p class="online-battle-connection" role="status"></p>
                <button class="btn" id="battle-leave">Leave room</button>`);
            this.root = this.online.container.querySelector('.online-panel');
            this.root.classList.add('online-battle-panel');
            this.root.querySelector('#battle-leave').onclick = () => this.online.confirmAction('leave');
            document.addEventListener('keydown', this._down);
            document.addEventListener('keyup', this._up);
            window.addEventListener('blur', this._blur);
            document.addEventListener('visibilitychange', this._blur);
        }
        this.room = room;
        const b = room.battle;
        if (this.pending && b.ack >= this.pending.seq) this.pending = null;
        this.root.querySelector('#online-battle-context').textContent = `${room.players[b.attacker].name} attacks ${b.move.slice(0, 2)} → ${b.move.slice(2, 4)}. You play ${room.you === 'w' ? 'White' : 'Black'}.`;
        const help = {
            'memory-match': 'Take turns revealing cards. Match one rank across the suits to win. Unmatched cards turn face-down after two seconds.',
            'mashing-battle': 'Mash your key or tap the button. Every five presses pushes toward your opponent. Push past the center before the 20-second timer ends.',
            'timing-battle': 'Wait for NOW!, then press your key or tap. Faster reactions push toward your opponent; an early press loses a point. Reach the far end to win.',
            'dodging-battle': 'Dodge the projectiles. Use WASD, IJKL, arrow keys, or the direction buttons to move your own piece. Last player standing wins.'
        };
        const favored = room.options.advantage === 'none' ? null : room.options.advantage === 'attacker' ? b.attacker : b.attacker === 'w' ? 'b' : 'w';
        const favoredName = favored === 'w' ? 'White' : 'Black';
        let advantage = '';
        if (b.gameId === 'memory-match') advantage = ` White needs ${b.targets.w} matching cards; Black needs ${b.targets.b}.`;
        else if (b.gameId === 'dodging-battle') advantage = favored ? ` ${favoredName} starts with an extra life.` : ' Each player has one life.';
        else if (LIVE.includes(b.gameId)) advantage = favored ? ` ${favoredName} starts one notch ahead.` : ' Both players start even.';
        this.root.querySelector('#online-battle-help').textContent = (help[b.gameId] || 'The designated player chooses from the host’s enabled games.') + advantage;
        const mode = b.outcome !== null ? 'result' : b.phase === 'choose' ? 'choose'
            : ['ready', 'paused'].includes(b.phase) ? 'ready' : b.gameId === 'memory-match' ? 'memory' : 'live';
        if (mode !== this.mode) {
            this.keys.clear();
            this.taps = 0;
            this.press = null;
            this.mode = mode;
            this.root.dataset.mode = mode;
            this._mount(mode);
        }
        this._refresh();
        if (!this.frame) this._animate();
    }

    _mount(mode) {
        const area = this.root.querySelector('#online-battle-play');
        area.innerHTML = '';
        const b = this.room.battle;
        if (mode === 'ready' || mode === 'result') {
            const button = this._button('', () => this.online.action(mode === 'ready' ? 'battle-ready' : 'continue'));
            button.id = 'battle-ready-action';
            area.append(button);
        } else if (mode === 'choose') {
            for (const game of this.room.options.selectedMinigames) {
                const button = this._button(ONLINE_GAMES[game], () => this.online.action('choose', { gameId: game }));
                button.disabled = b.choiceBy !== this.room.you;
                area.append(button);
            }
        } else if (mode === 'memory') {
            const grid = document.createElement('div');
            grid.className = 'online-card-grid';
            for (let i = 0; i < 52; i++) {
                const button = this._button('♠', () => this.online.action('flip', { index: i, turnNumber: this.room.battle.turnNumber }));
                button.className = 'online-card';
                button.dataset.index = i;
                grid.append(button);
            }
            area.append(grid);
        } else if (b.gameId === 'dodging-battle') {
            area.innerHTML = '<canvas class="online-dodge-canvas" width="400" height="400" aria-label="Dodging arena: White and Black avoid incoming projectiles"></canvas><p class="online-lives"></p><div class="online-direction-pad"></div>';
            const pad = area.querySelector('.online-direction-pad');
            for (const [label, key, arrow] of [['Up', 'ArrowUp', '↑'], ['Left', 'ArrowLeft', '←'], ['Down', 'ArrowDown', '↓'], ['Right', 'ArrowRight', '→']]) {
                const button = this._button(arrow, () => {});
                button.setAttribute('aria-label', `Move ${label.toLowerCase()}`);
                button.onpointerdown = event => {
                    event.preventDefault();
                    button.setPointerCapture(event.pointerId);
                    this.keys.add(key);
                    this.sendFrame();
                };
                const release = () => { this.keys.delete(key); this.sendFrame(); };
                button.onpointerup = release;
                button.onpointercancel = release;
                button.onlostpointercapture = release;
                pad.append(button);
            }
        } else {
            area.innerHTML = '<div class="online-tug-labels"><span>White</span><span>Black</span></div><div class="online-tug" role="meter" aria-label="Battle position" aria-valuemin="0" aria-valuemax="8"><span class="online-tug-marker">♚</span></div><p class="online-reactions"></p>';
            const button = this._button(b.gameId === 'mashing-battle' ? 'Mash!' : 'React!', () => this._tap());
            button.id = 'battle-tap';
            area.append(button);
            const label = document.createElement('p');
            label.textContent = `Keyboard: ${this.room.you === 'w' ? 'A' : 'L'} or Space. Each press counts once.`;
            area.append(label);
        }
    }

    _refresh() {
        const { battle: b, you, players } = this.room;
        const status = this.root.querySelector('#online-battle-status');
        if (this.mode === 'ready') {
            status.textContent = b.phase === 'paused' ? 'Connection interrupted. The battle is paused. Both players must be ready to resume.' : 'Read the controls, then get ready. The battle starts after both players confirm.';
            const button = this.root.querySelector('#battle-ready-action');
            button.disabled = b.startReady.includes(you) || this.online.busy;
            button.textContent = b.startReady.includes(you) ? 'Waiting for your opponent…' : b.phase === 'paused' ? 'Ready to resume' : 'Ready to battle';
        } else if (this.mode === 'result') {
            status.textContent = b.outcome === 'tie' ? 'A tie! Play the battle again.' : b.outcome === 'attacker' ? 'Attacker wins — the capture succeeds.' : 'Defender wins — the capture fails.';
            const button = this.root.querySelector('#battle-ready-action');
            button.disabled = b.ready.includes(you) || this.online.busy;
            button.textContent = b.ready.includes(you) ? 'Waiting for your opponent…' : b.outcome === 'tie' ? 'Play the tie again' : 'Return to board';
            if (b.gameId === 'memory-match' && !this.root.querySelector('.online-memory-winning')) {
                const cards = document.createElement('p');
                cards.className = 'online-memory-winning';
                cards.textContent = 'Matching cards: ' + Object.values(b.cards).map(cardText).join(' · ');
                this.root.querySelector('#online-battle-play').prepend(cards);
            }
        } else if (this.mode === 'choose') {
            status.textContent = b.choiceBy === you ? 'Your choice — pick a minigame.' : `Waiting for ${players[b.choiceBy].name} to choose.`;
        } else if (this.mode === 'memory') {
            status.textContent = `${players[b.turn].name}: match ${b.targets[b.turn]} cards of one rank. ${b.flipped.length}/${b.targets[b.turn]} revealed.`
                + (b.hideAt !== null ? ' Remember these cards…' : b.turn === you ? ' Your turn.' : ' Waiting for your opponent.');
            for (const button of this.root.querySelectorAll('.online-card')) {
                const value = b.cards[button.dataset.index];
                button.textContent = value === undefined ? '♠' : cardText(value);
                button.classList.toggle('online-card-revealed', value !== undefined);
                button.setAttribute('aria-label', value === undefined ? `Flip card ${+button.dataset.index + 1}` : `Card ${+button.dataset.index + 1}: ${cardText(value)}`);
                button.disabled = value !== undefined || b.turn !== you || b.hideAt !== null || this.online.busy;
            }
        }
    }

    _animate() {
        if (!this.id) return;
        const b = this.room.battle;
        this.root.querySelector('.online-battle-connection').textContent = !this.online.connected ? 'Reconnecting… Controls are paused.' : '';
        if (this.mode === 'live') {
            const now = this.now();
            const status = this.root.querySelector('#online-battle-status');
            const countdown = b.phase === 'countdown';
            if (countdown) status.textContent = `${b.extraLife ? 'Extra life — ' : ''}Starting in ${Math.max(0, Math.ceil(b.startAt - now))}…`;
            else if (b.gameId === 'mashing-battle') status.textContent = `${Math.max(0, b.endsAt - now).toFixed(1)} seconds — keep mashing!`;
            else if (b.gameId === 'timing-battle') status.textContent = b.stage === 'signal' ? 'NOW!' : b.stage === 'result' ? b.message : 'Wait for NOW!';
            else status.textContent = 'Dodge! Keep away from the incoming projectiles.';
            const tap = this.root.querySelector('#battle-tap');
            if (tap) tap.disabled = countdown || !this.online.connected || (b.gameId === 'timing-battle' && (b.stage === 'result' || b.reactions[this.room.you] !== undefined || !!this.press || !!this.pending?.press));
            if (b.gameId === 'dodging-battle') this._drawDodge();
            else {
                this.root.querySelector('.online-tug-marker').style.left = `${b.position / 8 * 100}%`;
                this.root.querySelector('.online-tug').setAttribute('aria-valuenow', b.position);
                this.root.querySelector('.online-reactions').textContent = b.gameId === 'mashing-battle'
                    ? `White: ${b.presses.w} presses · Black: ${b.presses.b} presses`
                    : ['w', 'b'].map(c => `${c === 'w' ? 'White' : 'Black'}: ${b.reactions[c] === -1 ? 'EARLY!' : b.reactions[c] === undefined ? '—' : b.reactions[c] + ' ms'}`).join(' · ');
            }
        }
        this.frame = requestAnimationFrame(() => this._animate());
    }

    _drawDodge() {
        const b = this.room.battle;
        const ctx = this.root.querySelector('canvas').getContext('2d');
        ctx.fillStyle = '#14231b'; ctx.fillRect(0, 0, 400, 400);
        ctx.strokeStyle = '#344a33'; ctx.lineWidth = 1;
        for (let i = 50; i < 400; i += 50) {
            ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 400); ctx.moveTo(0, i); ctx.lineTo(400, i); ctx.stroke();
        }
        // Short extrapolation smooths network snapshots; collisions remain server-owned.
        const dt = b.phase === 'playing' && this.online.connected ? Math.min(.12, (performance.now() - this.room._receivedAt) / 1000) : 0;
        for (const p of b.projectiles) {
            ctx.fillStyle = '#ff8b78'; ctx.beginPath();
            ctx.arc(p.x + p.vx * (120 + b.elapsed * 12) * dt, p.y + p.vy * (120 + b.elapsed * 12) * dt, 5, 0, Math.PI * 2); ctx.fill();
        }
        for (const c of ['w', 'b']) {
            const actor = b.actors[c];
            ctx.fillStyle = c === 'w' ? '#f0e4c6' : '#84bbbd';
            ctx.beginPath(); ctx.arc(actor.x, actor.y, 16, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#14231b'; ctx.font = 'bold 16px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(c.toUpperCase(), actor.x, actor.y);
        }
        this.root.querySelector('.online-lives').textContent = `White: ${b.actors.w.lives} ${b.actors.w.lives === 1 ? 'life' : 'lives'} · Black: ${b.actors.b.lives} ${b.actors.b.lives === 1 ? 'life' : 'lives'}`;
    }

    _key(event, down) {
        if (!this.live || ['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName)) return;
        const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
        if (this.room.battle.gameId === 'dodging-battle') {
            if (!['w', 'a', 's', 'd', 'i', 'j', 'k', 'l', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) return;
            event.preventDefault();
            if (down) this.keys.add(key); else this.keys.delete(key);
            if (!event.repeat) this.sendFrame();
        } else if (key === ' ' || key === (this.room.you === 'w' ? 'a' : 'l')) {
            event.preventDefault();
            if (down && !event.repeat) this._tap();
        }
    }

    _tap() {
        const b = this.room.battle;
        if (!this.live || !this.online.connected || b.phase !== 'playing') return;
        if (b.gameId === 'mashing-battle') this.taps = Math.min(8, this.taps + 1);
        else if (b.stage !== 'result' && b.reactions[this.room.you] === undefined && !this.press && !this.pending?.press) {
            this.press = { press: true, round: b.round, cue: b.cue };
            this.sendFrame();
        }
    }

    async sendFrame() {
        if (!this.live || this.sending || this.online.busy || document.hidden) return;
        this.sending = true;
        const id = this.id, generation = this.online.generation;
        if (!this.pending) {
            const directions = [['w', 'i', 'ArrowUp'], ['s', 'k', 'ArrowDown'], ['a', 'j', 'ArrowLeft'], ['d', 'l', 'ArrowRight']];
            const keys = directions.reduce((mask, group, index) => mask | (group.some(k => this.keys.has(k)) ? 1 << index : 0), 0);
            this.pending = { battleId: id, seq: this.room.battle.ack + 1, keys, taps: this.taps, ...this.press };
            this.taps = 0; this.press = null;
        }
        try {
            const data = await this.online._request(`/rooms/${this.online.code}/battle-input`, this.pending);
            if (this.id === id && generation === this.online.generation) this.online._accept(data.room);
        } catch (error) {
            if (this.id !== id || generation !== this.online.generation) return;
            this.online.connected = false;
            this._blur();
            if (error.status) {
                this.pending = null;
                await this.online._sync();
            }
        } finally {
            this.sending = false;
        }
    }

    _button(text, onClick) {
        const button = document.createElement('button');
        button.className = 'btn btn-primary'; button.textContent = text; button.onclick = onClick;
        return button;
    }

    destroy() {
        cancelAnimationFrame(this.frame);
        this.frame = null; this.id = null; this.mode = null; this.pending = null;
        this._blur();
        document.removeEventListener('keydown', this._down);
        document.removeEventListener('keyup', this._up);
        window.removeEventListener('blur', this._blur);
        document.removeEventListener('visibilitychange', this._blur);
    }
}
