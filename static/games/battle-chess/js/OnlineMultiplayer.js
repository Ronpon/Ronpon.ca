import { GameEvent, GameState } from './Constants.js';
import { OnlineBattleScreen, ONLINE_GAMES } from './OnlineBattleScreen.js';

const API = '/games/battle-chess/api';
const seatKey = code => `battle-chess-seat:${code}`;
const colorName = color => color === 'w' ? 'White' : 'Black';

/** Online games render authoritative snapshots; local games keep their existing flow. */
export class OnlineMultiplayer {
    constructor(app) {
        this.app = app;
        this.manager = app.gameManager;
        this.container = app.overlay;
        this.room = null;
        this.code = null;
        this.token = null;
        this.csrf = null;
        this.connected = false;
        this.busy = false;
        this.generation = 0;
        this.timer = null;
        this.battleScreen = new OnlineBattleScreen(this);
        this.confirming = null;
        this.bar = document.createElement('div');
        this.bar.id = 'online-bar';
        this.bar.hidden = true;
        this.bar.innerHTML = '<span role="status" id="online-status"></span><button class="btn" id="online-resign">Resign</button><button class="btn" id="online-leave">Leave room</button>';
        document.getElementById('canvas-container').before(this.bar);
        this.bar.querySelector('#online-resign').addEventListener('click', () => this.confirmAction('resign'));
        this.bar.querySelector('#online-leave').addEventListener('click', () => this.confirmAction('leave'));
        app.eventBus.on('showOnline', () => this.showMenu());
    }

    async init() {
        const invited = new URLSearchParams(location.search).get('room')?.toUpperCase();
        const last = this._stored('battle-chess-last');
        const code = invited || last;
        if (code && /^[A-HJ-NP-Z2-9]{6}$/.test(code)) {
            const token = this._stored(seatKey(code));
            if (token) {
                this._connect(code, token);
                this._panel('Reconnecting', '<p>Restoring your room…</p>');
                await this._sync();
                this._schedule();
            } else {
                this.showMenu(code);
            }
        } else {
            this.app.setupWizard.show();
        }
    }

    _stored(key, value) {
        try {
            if (value === null) sessionStorage.removeItem(key);
            else if (value !== undefined) sessionStorage.setItem(key, value);
            else return sessionStorage.getItem(key);
        } catch { /* Storage may be disabled; the current room still works. */ }
        return null;
    }

    async _request(path, body) {
        if (body !== undefined && !this.csrf) {
            this.csrf = (await this._request('/session')).csrfToken;
        }
        const sentAt = performance.now();
        const response = await fetch(API + path, {
            method: body === undefined ? 'GET' : 'POST',
            credentials: 'same-origin', cache: 'no-store',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrf || '',
                'X-Battle-Token': this.token || '' },
            ...(body === undefined ? {} : { body: JSON.stringify(body) }),
            signal: AbortSignal.timeout(10000)
        });
        const data = await response.json().catch(() => ({}));
        if (data.room) {
            data.room._receivedAt = performance.now();
            data.room._serverAt = data.room.serverTime + (performance.now() - sentAt) / 2000;
        }
        if (!response.ok) {
            if (response.status === 400 && !data.error) this.csrf = null;
            const error = new Error(data.error || (response.status === 429
                ? 'Too many requests. Please wait a minute.' : 'Request failed. Please try again.'));
            error.status = response.status;
            throw error;
        }
        return data;
    }

    showMenu(code = '') {
        this.app.setupWizard.hide();
        this._panel('Play Online', `
            <p>Invite a friend to a private, two-player room. The host plays White.</p>
            <label>Your name<input id="online-name" class="setup-name-input" maxlength="24" autocomplete="nickname" placeholder="Your name"></label>
            <fieldset id="online-settings"><legend>Host a game</legend>
                <label>Capture battles<select id="online-mode">${Object.entries(ONLINE_GAMES).map(([id, name]) => `<option value="${id}">${name}</option>`).join('')}<option value="mixed">Mix of minigames</option><option value="classic">None — classic chess</option></select></label>
                <div id="online-game-mix" hidden>
                    <p>Choose your games (listed in set order):</p>
                    ${Object.entries(ONLINE_GAMES).map(([id, name]) => `<label class="online-checkbox"><input type="checkbox" name="online-minigame" value="${id}" checked>${name}</label>`).join('')}
                    <label>Game selection<select id="online-selection"><option value="random">Random</option><option value="setOrder">Set order</option><option value="attackerChoice">Attacker chooses</option><option value="defenderChoice">Defender chooses</option></select></label>
                </div>
                <p class="online-hint">All five minigames support online play. Timed battles start when both players are ready and pause on disconnect.</p>
                <label>Battle advantage<select id="online-advantage"><option value="attacker">Attacker</option><option value="defender">Defender</option><option value="none">None — even match</option></select></label>
                <label class="online-checkbox"><input type="checkbox" id="online-loss"> Remove the attacking piece if it loses</label>
                <button class="btn btn-primary" id="online-create">Create room</button>
            </fieldset>
            <fieldset><legend>Join a friend</legend>
                <label>Room code<input id="online-code" class="setup-name-input" maxlength="6" autocapitalize="characters" autocomplete="off" spellcheck="false" placeholder="ABC234"></label>
                <button class="btn btn-primary" id="online-join">Join room</button>
            </fieldset>
            <button class="btn" id="online-back">Back</button>`);
        this.container.querySelector('#online-code').value = code;
        this.container.querySelector('#online-name').value = this._stored('battle-chess-name') || '';
        this.container.querySelector('#online-back').onclick = () => this.app.setupWizard.show();
        this.container.querySelector('#online-mode').onchange = event => {
            const classic = event.target.value === 'classic';
            this.container.querySelector('#online-advantage').disabled = classic;
            this.container.querySelector('#online-loss').disabled = classic;
            this.container.querySelector('#online-game-mix').hidden = event.target.value !== 'mixed';
        };
        this.container.querySelector('#online-create').onclick = () => this._enter(false);
        this.container.querySelector('#online-join').onclick = () => this._enter(true);
        this.container.querySelector('#online-code').onkeydown = event => {
            if (event.key === 'Enter') this._enter(true);
        };
    }

    async _enter(join) {
        if (this.busy) return;
        const name = this.container.querySelector('#online-name').value.trim();
        const code = this.container.querySelector('#online-code').value.trim().toUpperCase();
        if (!name) return this._message('Enter your name.');
        if (join && !/^[A-HJ-NP-Z2-9]{6}$/.test(code)) return this._message('Enter a valid six-character room code.');
        const body = { name, options: {
            mode: this.container.querySelector('#online-mode').value,
            advantage: this.container.querySelector('#online-advantage').value,
            attackerLosesPiece: this.container.querySelector('#online-loss').checked,
            selectedMinigames: [...this.container.querySelectorAll('[name="online-minigame"]:checked')].map(input => input.value),
            minigameMode: this.container.querySelector('#online-selection').value
        } };
        this.busy = true;
        this._disablePanel(true);
        this._message(join ? 'Joining room…' : 'Creating room…');
        try {
            this.token = join ? this._stored(seatKey(code)) : null;
            const data = await this._request(join ? `/rooms/${code}/join` : '/rooms', body);
            this._stored('battle-chess-name', name);
            this._connect(data.room.code, data.token);
            this._accept(data.room);
            this._schedule();
        } catch (error) {
            this._message(error.message);
        } finally {
            this.busy = false;
            this._disablePanel(false);
            // Reapply per-action disabled states after the connection completes.
            if (this.room) this._renderRoom();
        }
    }

    _connect(code, token) {
        this.generation++;
        this.code = code;
        this.token = token;
        this.room = null;
        this.manager.online = this;
        this.manager.setState(GameState.SETUP);
        this._stored(seatKey(code), token);
        this._stored('battle-chess-last', code);
        this.bar.hidden = false;
        document.body.classList.add('online-active');
    }

    _schedule() {
        clearTimeout(this.timer);
        if (this.code) this.timer = setTimeout(async () => {
            if (!this.busy) {
                if (this.battleScreen.live) await this.battleScreen.sendFrame();
                else await this._sync();
            }
            this._schedule();
        }, !this.connected ? 1000 : this.battleScreen.live ? 100 : this.room?.phase === 'battle' ? 250 : 1200);
    }

    async _sync() {
        const generation = this.generation;
        try {
            const data = await this._request(`/rooms/${this.code}`);
            if (generation !== this.generation) return;
            this._accept(data.room);
        } catch (error) {
            if (generation !== this.generation) return;
            this.connected = false;
            this._updateBar();
            if (error.status === 403 || error.status === 404) {
                const code = this.code;
                this._disconnect();
                this.showMenu(code);
                this._message(error.message);
            } else {
                this._message('Connection interrupted. Reconnecting automatically…');
                if (!this.room) {
                    this._panel('Connection interrupted', '<p>Reconnecting automatically. You can also return to setup.</p><button class="btn" id="online-cancel-reconnect">Back</button>');
                    this.container.querySelector('#online-cancel-reconnect').onclick = () => {
                        this._disconnect(false);
                        this.app.setupWizard.show();
                    };
                }
            }
        }
    }

    _accept(room) {
        this.connected = true;
        if (this.room && room.version < this.room.version) return;
        if (room.players[room.you]?.left) {
            this._disconnect();
            this.app.setupWizard.show();
            return;
        }
        const changed = !this.room || room.version !== this.room.version;
        const boardChanged = !this.room || this.room.fen !== room.fen || this.room.phase !== room.phase || this.room.game !== room.game;
        if (room.phase === 'playing' && (!this.room || ['waiting', 'finished'].includes(this.room.phase))) {
            this.app.checkWarning.reset();
        }
        this.room = room;
        this._updateBar();
        if (!changed) return;
        if (boardChanged) {
            this.app.inputHandler.cancelPromotion();
            this.app.promotionDialog.panel = null;
            this.manager.chess.load(room.fen);
        }
        this.manager.config = {
            players: ['w', 'b'].map(color => room.players[color] || { name: 'Waiting for opponent', color }),
            selectedMinigames: room.options.selectedMinigames || (room.options.mode === 'classic' ? [] : [room.options.mode]),
            minigameMode: room.options.minigameMode || 'setOrder', minigameAdvantage: room.options.advantage,
            attackerLosesPiece: room.options.attackerLosesPiece, playerCount: 2
        };
        this.manager.pendingMove = null;
        this.manager.minigameState.currentIndex = room.battleIndex || 0;
        const nextState = { waiting: GameState.SETUP, playing: GameState.PLAYING,
            battle: GameState.MINIGAME, finished: GameState.GAME_OVER }[room.phase];
        if (this.manager.state !== nextState) this.manager.setState(nextState);
        const state = this.manager.getGameState();
        state.moveHistory = room.lastMove ? [room.lastMove] : [];
        if (boardChanged) {
            this.app.board.clearSelection();
            this.app.eventBus.emit(GameEvent.BOARD_UPDATED, state);
        }
        this._renderRoom();
    }

    canMove() {
        return !!(this.room && this.connected && !this.busy && this.room.phase === 'playing'
            && this.room.you === this.manager.chess.turn());
    }

    attemptMove(from, to, promotion) {
        if (!this.canMove()) return null;
        this.action('move', { from, to, promotion });
        return { pending: true };
    }

    async action(type, extra = {}) {
        if (this.busy || !this.code || !this.room) return;
        if (!this.connected) return this._message('Reconnecting. Please wait before playing.');
        this.busy = true;
        this._disablePanel(true);
        const generation = this.generation;
        let failure = null;
        try {
            const original = this.room;
            const payload = {
                id: crypto.randomUUID(), version: this.room.version, game: this.room.game,
                battleId: this.room.battle?.id, type, ...extra
            };
            let data;
            try {
                data = await this._request(`/rooms/${this.code}/actions`, payload);
            } catch (error) {
                if (error.status !== 409) throw error;
                await this._sync();
                // These acknowledgements commute: both players commonly click
                // together. Retry against the new revision only in the same round.
                const sameRound = this.room?.game === original.game;
                const retry = sameRound && ((type === 'continue' && this.room.battle?.id === original.battle?.id)
                    || (type === 'rematch' && this.room.phase === 'finished'));
                if (!retry) throw error;
                payload.version = this.room.version;
                data = await this._request(`/rooms/${this.code}/actions`, payload);
            }
            if (generation !== this.generation) return;
            if (type === 'leave') {
                this._disconnect();
                this.app.setupWizard.show();
            } else this._accept(data.room);
        } catch (error) {
            if (generation !== this.generation) return;
            await this._sync();
            failure = error.message;
        } finally {
            this.busy = false;
            this._disablePanel(false);
            if (this.room) this._renderRoom();
            if (failure) this._message(failure);
        }
    }

    _updateBar() {
        if (!this.room) return;
        const opponent = this.room.players[this.room.you === 'w' ? 'b' : 'w'];
        this.bar.querySelector('#online-status').textContent = !this.connected ? 'Connection lost — reconnecting…'
            : `Room ${this.code} · You are ${colorName(this.room.you)} · ` + (!opponent ? 'Waiting for a friend'
                : opponent.left ? 'Opponent left' : opponent.online ? `${opponent.name} connected` : 'Opponent disconnected — waiting for them to return');
        this.bar.querySelector('#online-resign').hidden = !['playing', 'battle'].includes(this.room.phase);
    }

    _rules() {
        const options = this.room.options;
        if (options.mode === 'classic') return 'Classic chess — captures happen without a battle.';
        const games = options.selectedMinigames || [options.mode];
        const advantage = games.length === 1 && games[0] === 'highest-card'
            ? options.advantage === 'none' ? 'Ties are replayed' : `${options.advantage} wins ties`
            : options.advantage === 'none' ? 'No advantage' : `${options.advantage} advantage`;
        return `${games.map(id => ONLINE_GAMES[id]).join(', ')} · ${advantage} · `
            + (options.attackerLosesPiece ? 'Losing attackers are removed.' : 'Losing attackers stay on the board.')
            + ' A checked attacker keeps the turn to answer check after a failed capture.';
    }

    _renderRoom() {
        const room = this.room;
        if (!room) return;
        if (this.confirming && this.confirming.game === room.game && room.phase !== 'finished') return;
        this.confirming = null;
        if (room.phase === 'battle') {
            this.battleScreen.update(room);
            return;
        }
        this.battleScreen.destroy();
        if (room.phase === 'playing') {
            this.container.classList.remove('active');
            this.container.innerHTML = '';
            return;
        }
        if (room.phase === 'waiting') {
            this._panel('Waiting for your friend', `
                <p>You play White. Share this room code or invite link.</p>
                <strong class="online-room-code">${room.code}</strong>
                <label>Invite link<input id="online-invite" class="setup-name-input" readonly></label>
                <button class="btn btn-primary" id="online-copy">Copy invite link</button>
                <p id="online-rules"></p><p>The game starts when your friend joins.</p>`);
            this.container.querySelector('#online-rules').textContent = this._rules();
            const input = this.container.querySelector('#online-invite');
            input.value = `${location.origin}/games/battle-chess?room=${room.code}`;
            this.container.querySelector('#online-copy').onclick = async () => {
                try { await navigator.clipboard.writeText(input.value); this._message('Invite link copied.'); }
                catch { input.focus(); input.select(); this._message('Copy the selected invite link.'); }
            };
        } else {
            this._panel('Game Over', '<p id="online-result"></p><button class="btn btn-primary" id="online-rematch">Play again</button>');
            const reasons = { 'checkmate': 'Checkmate.', 'stalemate': 'Stalemate.', 'draw': 'Draw.',
                'resignation': 'Resigned.', 'opponent-left': 'A player left the room.',
                'battle-in-check': 'The attacker lost a battle while in check.',
                'king-lost': 'The failed attack would lose or expose the king.' };
            const result = room.result;
            const winner = result.winner && room.players[result.winner];
            this.container.querySelector('#online-result').textContent = `${reasons[result.reason] || ''} ${winner ? `${winner.name} (${colorName(result.winner)}) wins!` : 'Game ended in a draw.'}`;
            const button = this.container.querySelector('#online-rematch');
            const unavailable = Object.values(room.players).some(p => !p || p.left);
            button.disabled = unavailable || room.rematch.includes(room.you) || this.busy;
            button.textContent = unavailable ? 'Create a new room to play again' : room.rematch.includes(room.you)
                ? 'Waiting for your opponent…' : room.rematch.length ? 'Accept rematch' : 'Play again';
            button.onclick = () => this.action('rematch');
        }
        const leave = document.createElement('button');
        leave.className = 'btn';
        leave.textContent = 'Leave room';
        leave.onclick = () => this.confirmAction('leave');
        this.container.querySelector('.online-panel').appendChild(leave);
    }

    confirmAction(type) {
        if (this.busy) return;
        const active = ['playing', 'battle'].includes(this.room?.phase);
        if (type === 'leave' && !active) return this.action('leave');
        this.confirming = { game: this.room.game };
        this.battleScreen.destroy();
        this._panel(type === 'resign' ? 'Resign this game?' : 'Leave this room?',
            '<p>Your opponent will win this game.</p><button class="btn btn-primary" id="online-confirm">Confirm</button><button class="btn" id="online-cancel">Keep playing</button>');
        this.container.querySelector('#online-confirm').onclick = () => this.action(type);
        this.container.querySelector('#online-cancel').onclick = () => { this.confirming = null; this._renderRoom(); };
    }

    _disconnect(forget = true) {
        clearTimeout(this.timer);
        this.battleScreen.destroy();
        this.confirming = null;
        this.generation++;
        if (forget) this._stored(seatKey(this.code), null);
        this._stored('battle-chess-last', null);
        this.code = null;
        this.token = null;
        this.room = null;
        this.connected = false;
        this.manager.online = null;
        this.app.inputHandler.cancelPromotion();
        this.manager.reset();
        this.app.checkWarning.reset();
        this.bar.hidden = true;
        document.body.classList.remove('online-active');
        this.app.turnIndicator.textContent = 'Battle Chess';
    }

    _panel(title, html) {
        this.container.innerHTML = '<section class="overlay-panel online-panel" role="dialog" aria-modal="true" aria-labelledby="online-title"><h2 id="online-title"></h2>'
            + html + '<p class="online-message" role="status" aria-live="polite"></p></section>';
        this.container.querySelector('h2').textContent = title;
        this.container.classList.add('active');
    }

    _message(message) {
        const element = this.container.querySelector('.online-message');
        if (element) element.textContent = message;
        else this.bar.querySelector('#online-status').textContent = message;
    }

    _disablePanel(disabled) {
        this.container.querySelectorAll('.online-panel button, .online-battle-screen button').forEach(button => {
            if (disabled) {
                button.dataset.wasDisabled = String(button.disabled);
                button.disabled = true;
            } else if ('wasDisabled' in button.dataset) {
                button.disabled = button.dataset.wasDisabled === 'true';
                delete button.dataset.wasDisabled;
            }
        });
    }
}
