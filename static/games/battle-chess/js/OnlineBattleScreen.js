import { HighestCard } from './minigames/HighestCard.js';
import { MemoryMatch } from './minigames/MemoryMatch.js';
import { MashingBattle } from './minigames/MashingBattle.js';
import { TimingBattle } from './minigames/TimingBattle.js';
import { DodgingBattle } from './minigames/DodgingBattle.js';
import { createBattleLayout, createBattleResult, captureConsequence } from './ui/BattleLayout.js';

export const ONLINE_GAMES = {
    'highest-card': 'Highest Card', 'memory-match': 'Memory Match',
    'mashing-battle': 'Mashing Battle', 'timing-battle': 'Timing Battle',
    'dodging-battle': 'Dodging Battle'
};
const GAMES = { 'highest-card': HighestCard, 'memory-match': MemoryMatch,
    'mashing-battle': MashingBattle, 'timing-battle': TimingBattle, 'dodging-battle': DodgingBattle };
const LIVE = ['mashing-battle', 'timing-battle', 'dodging-battle'];

/** Local presentation driven exclusively by authoritative room snapshots. */
export class OnlineBattleScreen {
    constructor(online) {
        this.online = online;
        this.id = null;
        this.epoch = 0;
        this.keys = new Set();
        this.taps = 0;
        this.press = null;
        this._down = event => this._key(event, true);
        this._up = event => this._key(event, false);
        this._blur = () => {
            this.keys.clear(); this.taps = 0; this.press = null; this.dirty = true;
        };
    }

    get live() { return !!(this.id && LIVE.includes(this.room.battle.gameId) && this.room.battle.outcome === null); }
    now() { return this.room._serverAt + (performance.now() - this.room._receivedAt) / 1000; }

    update(room) {
        if (this.id !== room.battle.id) this._create(room);
        this.room = room;
        const b = room.battle;
        if (this.pending && b.ack >= this.pending.seq) this.pending = null;
        const mode = b.outcome !== null ? 'result' : b.phase === 'choose' ? 'choose'
            : ['ready', 'paused'].includes(b.phase) ? 'ready' : LIVE.includes(b.gameId) ? 'live' : 'cards';
        if (mode !== this.mode) { this._blur(); this.mode = mode; }
        this.root.dataset.mode = mode;
        if (mode === 'result' && this.resultAt === null) this.resultAt = performance.now();
        this._refresh();
        if (!this.frame) this._animate();
    }

    _create(room) {
        this.destroy();
        this.id = room.battle.id;
        this.room = room;
        const GameClass = GAMES[room.battle.gameId];
        if (!GameClass) {
            this.online._panel('Choose a Minigame', '<p id="online-battle-status" role="status"></p><div id="online-battle-play"></div>');
            this.root = this.online.container.querySelector('.online-panel');
            for (const id of room.options.selectedMinigames) {
                const button = this._button(ONLINE_GAMES[id], () => this.online.action('choose', { gameId: id }));
                this.root.querySelector('#online-battle-play').append(button);
            }
            return;
        }
        this.game = new GameClass();
        const players = ['w', 'b'].map(color => room.players[color]);
        const controls = players.map((player, index) => index === (room.you === 'w' ? 0 : 1)
            ? this.game.controls[index === 0 ? 'player1' : 'player2'] + '\nYou · ' + (index === 0 ? 'White' : 'Black')
            : 'Opponent controls this player');
        this.root = createBattleLayout({ players, attackerColor: room.battle.attacker,
            advantage: room.options.advantage, gameEntry: this.game, controls });
        this.root.classList.add('online-battle-screen');
        this.root.dataset.game = room.battle.gameId;
        this.online.container.replaceChildren(this.root);
        this.online.container.classList.add('active');
        this.arena = this.root.querySelector('#mg-arena');
        this.surface = document.createElement('div');
        this.surface.className = 'online-game-surface';
        this.arena.append(this.surface);
        const center = this.root.querySelector('.mg-center');
        const context = document.createElement('p');
        context.id = 'online-battle-context';
        center.querySelector('.mg-title').after(context);
        center.insertAdjacentHTML('beforeend', '<p id="online-battle-status" role="status"></p><div class="online-control-tray"></div><div class="online-battle-footer"><p class="online-battle-connection" role="status"></p><p class="online-message" role="status"></p><button class="btn" id="battle-leave">Leave room</button></div>');
        this.root.querySelector('#battle-leave').onclick = () => this.online.confirmAction('leave');
        const network = {
            you: room.you,
            canAct: () => this.online.connected && !this.online.busy && !this.explaining,
            action: (type, data) => this.online.action(type, data),
            battle: () => this.room.battle
        };
        this.game.init(this.surface, { players, attackerColor: room.battle.attacker,
            advantage: room.options.advantage, network, onEnd: () => {} });
        this.game.start();
        if (!LIVE.includes(room.battle.gameId)) {
            this.explaining = !this.online._stored('battle-chess-explained:' + room.battle.gameId);
        }
        this._mountControls();
        document.addEventListener('keydown', this._down);
        document.addEventListener('keyup', this._up);
        window.addEventListener('blur', this._blur);
        document.addEventListener('visibilitychange', this._blur);
    }

    _mountControls() {
        const tray = this.root.querySelector('.online-control-tray');
        const game = this.room.battle.gameId;
        if (game === 'dodging-battle') {
            this.game.canvas.classList.add('online-dodge-canvas');
            this.game.canvas.ariaLabel = 'Dodging arena: White and Black avoid incoming projectiles';
            tray.innerHTML = '<p class="online-lives"></p><div class="online-direction-pad"></div>';
            for (const [label, key, arrow] of [['Up', 'ArrowUp', '↑'], ['Left', 'ArrowLeft', '←'], ['Down', 'ArrowDown', '↓'], ['Right', 'ArrowRight', '→']]) {
                const button = this._button(arrow, () => {});
                button.ariaLabel = 'Move ' + label.toLowerCase();
                button.onpointerdown = event => {
                    if (!this.online.connected || this.room.battle.phase !== 'playing') return;
                    event.preventDefault(); button.setPointerCapture(event.pointerId);
                    this.keys.add(key); this.dirty = true; this.sendFrame();
                };
                const release = () => { this.keys.delete(key); this.dirty = true; this.sendFrame(); };
                button.onpointerup = release;
                button.onpointercancel = release;
                button.onlostpointercapture = release;
                tray.querySelector('.online-direction-pad').append(button);
            }
        } else if (LIVE.includes(game)) {
            const button = this._button(game === 'mashing-battle' ? 'Mash!' : 'React!', () => this._tap());
            button.id = 'battle-tap';
            tray.append(button);
            const reactions = document.createElement('p');
            reactions.className = 'online-reactions';
            tray.append(reactions);
        }
    }

    _refresh() {
        const { battle: b, you, players } = this.room;
        const status = this.root.querySelector('#online-battle-status');
        if (!this.game) {
            status.textContent = b.choiceBy === you ? 'Your choice — pick a minigame.' : 'Waiting for ' + players[b.choiceBy].name + ' to choose.';
            this.root.querySelectorAll('button').forEach(button => { button.disabled = b.choiceBy !== you || this.online.busy; });
            return;
        }
        this.root.querySelector('#online-battle-context').textContent = players[b.attacker].name + ' attacks ' + b.move.slice(0, 2) + ' → ' + b.move.slice(2, 4) + '. You play ' + (you === 'w' ? 'White' : 'Black') + '.';
        this.game.applyNetworkState(b, this.now(), this._directions(), this.online.connected,
            this.room._receivedAt, this.now() - this.room.serverTime);
        const countdown = b.phase === 'countdown';
        if (this.mode === 'ready') status.textContent = b.phase === 'paused'
            ? 'Connection interrupted. The battle is paused. Both players must be ready to resume.'
            : 'Read the controls, then get ready. The battle starts after both players confirm.';
        else if (this.mode === 'result') status.textContent = b.outcome === 'tie' ? 'A tie! Play the battle again.'
            : b.outcome === 'attacker' ? 'Attacker wins — the capture succeeds.' : 'Defender wins — the capture fails.';
        else if (countdown) status.textContent = (b.extraLife ? 'Extra life — ' : '') + 'Starting in ' + Math.max(0, Math.ceil(b.startAt - this.now())) + '…';
        else if (b.gameId === 'highest-card') status.textContent = Object.keys(b.picks).length === 2
            ? 'Both players have chosen! Reveal the cards together.'
            : (this.game.currentPicker === (you === 'w' ? 0 : 1) ? 'Your turn — choose a face-down card.' : 'Waiting for your opponent to choose a card…');
        else if (b.gameId === 'memory-match') status.textContent = players[b.turn].name + ': match ' + b.targets[b.turn] + ' cards of one rank. ' + b.flipped.length + '/' + b.targets[b.turn] + ' revealed.'
            + (b.hideAt !== null ? ' Remember these cards…' : b.turn === you ? ' Your turn.' : ' Waiting for your opponent.');
        else if (b.gameId === 'mashing-battle') status.textContent = Math.max(0, b.endsAt - this.now()).toFixed(1) + ' seconds — keep mashing!';
        else if (b.gameId === 'timing-battle') status.textContent = b.stage === 'signal' ? 'NOW!' : b.stage === 'result' ? b.message : 'Wait for NOW!';
        else status.textContent = 'Dodge! Keep away from the incoming projectiles.';
        const tap = this.root.querySelector('#battle-tap');
        if (tap) tap.disabled = b.phase !== 'playing' || b.outcome !== null || !this.online.connected
            || (b.gameId === 'timing-battle' && (b.stage === 'result' || b.reactions[you] !== undefined || !!this.press || !!this.pending?.press));
        const reactions = this.root.querySelector('.online-reactions');
        if (reactions) reactions.textContent = b.gameId === 'mashing-battle'
            ? 'White: ' + b.presses.w + ' presses · Black: ' + b.presses.b + ' presses'
            : ['w', 'b'].map(c => (c === 'w' ? 'White' : 'Black') + ': ' + (b.reactions[c] === -1 ? 'EARLY!' : b.reactions[c] === undefined ? '—' : b.reactions[c] + ' ms')).join(' · ');
        const lives = this.root.querySelector('.online-lives');
        if (lives) lives.textContent = ['w', 'b'].map(c => (c === 'w' ? 'White' : 'Black') + ': ' + b.actors[c].lives + (b.actors[c].lives === 1 ? ' life' : ' lives')).join(' · ');
        this.root.querySelector('.online-control-tray').hidden = this.mode !== 'live';
        this._overlay();
    }

    _overlay() {
        const b = this.room.battle;
        const resultVisible = b.outcome !== null && performance.now() - this.resultAt >= (b.gameId === 'highest-card' ? 2500 : b.gameId === 'memory-match' ? 1600 : 800);
        const kind = resultVisible ? 'result' : this.mode === 'ready' ? 'ready'
            : b.outcome === null && this.explaining ? 'explanation'
            : b.gameId === 'dodging-battle' && b.phase === 'countdown' ? 'countdown' : null;
        if (kind !== this.overlayKind) {
            this.overlay?.remove();
            this.overlay = null;
            this.overlayKind = kind;
            if (kind === 'result') {
                const isKing = this.online.manager.chess.get(b.move.slice(0, 2))?.type === 'k';
                this.overlay = createBattleResult({
                    result: { attackerWins: b.outcome === 'attacker', tie: b.outcome === 'tie' },
                    players: ['w', 'b'].map(c => this.room.players[c]), attackerColor: b.attacker,
                    consequence: b.outcome === 'tie' ? 'Replay the same minigame with the same settings.'
                        : captureConsequence(b.outcome === 'attacker', isKing, this.room.options.attackerLosesPiece),
                    buttonText: b.outcome === 'tie' ? 'Play the tie again' : 'Return to board',
                    onContinue: () => this.online.action('continue')
                });
                this.overlay.querySelector('button').id = 'battle-ready-action';
            } else if (kind) {
                this.overlay = document.createElement('div');
                this.overlay.className = 'mg-explanation';
                const description = document.createElement('p');
                description.className = 'mg-explanation-text';
                description.textContent = kind === 'countdown' ? b.extraLife
                    ? this.room.players[b.extraLife].name + ' has ' + b.actors[b.extraLife].lives + ' life remaining' : 'Get ready to dodge!'
                    : this.game.description;
                this.overlay.append(description);
                if (kind === 'countdown') {
                    const count = document.createElement('p');
                    count.className = 'mg-countdown';
                    this.overlay.append(count);
                } else {
                    const button = this._button(kind === 'explanation' ? 'Got It' : 'Ready to battle', () => {
                        if (kind === 'explanation') {
                            this.explaining = false;
                            this.online._stored('battle-chess-explained:' + b.gameId, '1');
                            this._refresh();
                        } else this.online.action('battle-ready');
                    });
                    button.id = 'battle-ready-action';
                    this.overlay.append(button);
                }
            }
            if (this.overlay) this.arena.append(this.overlay);
        }
        const button = this.overlay?.querySelector('button');
        if (button && kind !== 'explanation') {
            const waiting = (kind === 'result' ? b.ready : b.startReady).includes(this.room.you);
            button.disabled = waiting || this.online.busy || !this.online.connected;
            button.textContent = waiting ? 'Waiting for your opponent…' : kind === 'result'
                ? b.outcome === 'tie' ? 'Play the tie again' : 'Return to board'
                : b.phase === 'paused' ? 'Ready to resume' : 'Ready to battle';
        }
        const countdown = this.overlay?.querySelector('.mg-countdown');
        if (countdown) countdown.textContent = Math.max(0, Math.ceil(b.startAt - this.now()));
    }

    _animate() {
        if (!this.id) return;
        if (this.game) {
            this.root.querySelector('.online-battle-connection').textContent = this.online.connected ? '' : 'Reconnecting… Controls are paused.';
            if (this.live) this._refresh();
            else this._overlay();
        }
        this.frame = requestAnimationFrame(() => this._animate());
    }

    _key(event, down) {
        if (!this.live || ['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName)) return;
        if (this.room.battle.phase !== 'playing') return;
        const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
        if (key === ' ' && event.target.tagName === 'BUTTON' && event.target.id !== 'battle-tap') return;
        if (this.room.battle.gameId === 'dodging-battle') {
            if (!['w', 'a', 's', 'd', 'i', 'j', 'k', 'l', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) return;
            event.preventDefault();
            if (down) this.keys.add(key); else this.keys.delete(key);
            if (!event.repeat) { this.dirty = true; this.sendFrame(); }
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
        } else return;
        this.dirty = true;
        this.sendFrame();
    }

    _directions() {
        const directions = [['w', 'i', 'ArrowUp'], ['s', 'k', 'ArrowDown'], ['a', 'j', 'ArrowLeft'], ['d', 'l', 'ArrowRight']];
        return directions.reduce((mask, group, index) => mask | (group.some(k => this.keys.has(k)) ? 1 << index : 0), 0);
    }

    async sendFrame() {
        if (!this.live || this.sending || this.online.busy || document.hidden) return;
        this.sending = true;
        const id = this.id, epoch = this.epoch, generation = this.online.generation;
        if (!this.pending) {
            this.pending = { battleId: id, seq: this.room.battle.ack + 1, keys: this._directions(), taps: this.taps, ...this.press };
            this.taps = 0; this.press = null; this.dirty = false;
        }
        try {
            const data = await this.online._request('/rooms/' + this.online.code + '/battle-input', this.pending);
            if (this.epoch === epoch && generation === this.online.generation) this.online._accept(data.room);
        } catch (error) {
            if (this.epoch !== epoch || generation !== this.online.generation) return;
            this.online.connected = false;
            this._blur();
            if (error.status) { this.pending = null; await this.online._sync(); }
        } finally {
            if (this.epoch === epoch) {
                this.sending = false;
                // Flush queued input without waiting for the next heartbeat.
                if (this.live && this.dirty && this.online.connected) this.sendFrame();
            }
        }
    }

    _button(text, onClick) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-primary'; button.textContent = text; button.onclick = onClick;
        return button;
    }

    destroy() {
        this.epoch++;
        cancelAnimationFrame(this.frame);
        this.frame = null; this.id = null; this.mode = null; this.pending = null;
        this.sending = false; this.resultAt = null; this.overlayKind = null;
        this.overlay?.remove(); this.overlay = null;
        this.game?.destroy(); this.game = null;
        this._blur();
        document.removeEventListener('keydown', this._down);
        document.removeEventListener('keyup', this._up);
        window.removeEventListener('blur', this._blur);
        document.removeEventListener('visibilitychange', this._blur);
    }
}
