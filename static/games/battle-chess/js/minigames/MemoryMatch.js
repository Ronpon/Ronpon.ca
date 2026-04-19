import { BaseMinigame } from './BaseMinigame.js';

/**
 * Memory Match — card memory minigame.
 *
 * 52 cards face-down in 4 rows of 13. Players take turns flipping cards,
 * trying to match all 4 suits of the same value (e.g. all four 7s).
 *
 * Each turn: flip up to N cards (4 normally, 3 with advantage).
 * After the Nth card is flipped, all cards flip back after 2 seconds.
 * First player to match N cards of the same value wins.
 *
 * Advantage: advantaged player only needs to match 3 (and flips 3 per turn).
 */
export class MemoryMatch extends BaseMinigame {
    constructor() {
        super();
        this.id = 'memory-match';
        this.name = 'Memory Match';
        this.thumbnail = '🧠';
        this.category = 'Skill';
        this.description = 'Flip cards and find a matching set! First to match all suits of one value wins.';
        this.controls = {
            player1: 'Click cards',
            player2: 'Click cards'
        };
    }

    init(container, config) {
        super.init(container, config);

        // Determine match requirements based on advantage
        this.attackerIdx = this.attackerColor === 'w' ? 0 : 1;
        this.defenderIdx = this.attackerColor === 'w' ? 1 : 0;

        // Cards per turn & match target per player
        // advantaged player: 3 flips, needs 3 matches
        // non-advantaged (or both if none): 4 flips, needs 4 matches
        this.playerFlips = [4, 4];
        this.playerTarget = [4, 4];
        if (this.advantage === 'attacker') {
            this.playerFlips[this.attackerIdx] = 3;
            this.playerTarget[this.attackerIdx] = 3;
        } else if (this.advantage === 'defender') {
            this.playerFlips[this.defenderIdx] = 3;
            this.playerTarget[this.defenderIdx] = 3;
        }

        // Dynamic description
        if (this.advantage === 'attacker') {
            this.description = 'Flip cards and find a matching set! The attacker only needs to match 3 cards (flips 3 per turn). The defender must match all 4 suits of one value.';
        } else if (this.advantage === 'defender') {
            this.description = 'Flip cards and find a matching set! The defender only needs to match 3 cards (flips 3 per turn). The attacker must match all 4 suits of one value.';
        } else {
            this.description = 'Flip cards and find a matching set! First to match all 4 suits of one value wins.';
        }

        // Build & shuffle deck
        this.suits = ['♠', '♥', '♦', '♣'];
        this.suitColors = { '♠': '#222', '♥': '#c0392b', '♦': '#c0392b', '♣': '#222' };
        this.values = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];

        this.deck = [];
        for (const suit of this.suits) {
            for (const val of this.values) {
                this.deck.push({ suit, value: val });
            }
        }
        this._shuffle(this.deck);

        // Card state: 'down' | 'up' | 'matched'
        this.cardState = new Array(52).fill('down');

        // Turn state
        this.currentPlayer = this.attackerIdx; // attacker goes first
        this.flippedThisTurn = []; // indices of cards flipped this turn
        this.turnLocked = false; // prevent clicks during flip-back delay

        this._onClick = this._onClick.bind(this);
    }

    start() {
        this.container.innerHTML = '';
        this.container.style.display = 'flex';
        this.container.style.flexDirection = 'column';
        this.container.style.alignItems = 'center';
        this.container.style.justifyContent = 'flex-start';
        this.container.style.padding = '12px';
        this.container.style.gap = '10px';
        this.container.style.overflowY = 'auto';

        // Turn indicator bar
        this._turnBar = document.createElement('div');
        this._turnBar.style.cssText = 'display:flex; align-items:center; justify-content:center; gap:10px; min-height:30px;';
        this.container.appendChild(this._turnBar);

        // Card grid
        this._grid = document.createElement('div');
        this._grid.style.cssText = 'display:grid; grid-template-columns:repeat(13,1fr); gap:4px; max-width:620px; width:100%;';
        this.container.appendChild(this._grid);

        // Build card elements
        this._cardEls = [];
        for (let i = 0; i < 52; i++) {
            const el = document.createElement('div');
            el.className = 'hc-card hc-card-back';
            el.dataset.index = i;
            el.innerHTML = '<span class="hc-card-inner">🂠</span>';
            this._grid.appendChild(el);
            this._cardEls.push(el);
        }

        // Player status area (counters)
        this._statusBar = document.createElement('div');
        this._statusBar.style.cssText = 'display:flex; justify-content:center; gap:40px; margin-top:4px;';
        this.container.appendChild(this._statusBar);

        this._grid.addEventListener('click', this._onClick);
        this._updateUI();
    }

    destroy() {
        if (this._grid) this._grid.removeEventListener('click', this._onClick);
        if (this._flipTimeout) clearTimeout(this._flipTimeout);
        super.destroy();
    }

    // ── Click handling ───────────────────────────────────

    _onClick(e) {
        if (this.turnLocked || this._destroyed) return;

        const cardEl = e.target.closest('.hc-card');
        if (!cardEl) return;
        const idx = parseInt(cardEl.dataset.index);

        // Can only flip face-down cards
        if (this.cardState[idx] !== 'down') return;

        // Flip card up
        this.cardState[idx] = 'up';
        this.flippedThisTurn.push(idx);
        this._renderCard(idx);

        const maxFlips = this.playerFlips[this.currentPlayer];

        // Check if this turn's flips are done
        if (this.flippedThisTurn.length >= maxFlips) {
            this.turnLocked = true;
            // Check for a match
            const matchResult = this._checkMatch();
            if (matchResult) {
                // Winner!
                setTimeout(() => {
                    if (!this._destroyed) this._handleWin(matchResult);
                }, 800);
            } else {
                // No match — show cards for 2 seconds, then flip back
                this._flipTimeout = setTimeout(() => {
                    if (this._destroyed) return;
                    this._flipBackTurn();
                    this._switchTurn();
                }, 2000);
            }
        }

        this._updateUI();
    }

    _checkMatch() {
        // Gather the values of flipped cards this turn
        const flippedCards = this.flippedThisTurn.map(i => this.deck[i]);
        const target = this.playerTarget[this.currentPlayer];

        // Count occurrences of each value among the flipped cards
        const valueCounts = {};
        for (const card of flippedCards) {
            valueCounts[card.value] = (valueCounts[card.value] || 0) + 1;
        }

        // Check if any value appears >= target times
        for (const [value, count] of Object.entries(valueCounts)) {
            if (count >= target) {
                return { value, count };
            }
        }
        return null;
    }

    _flipBackTurn() {
        for (const idx of this.flippedThisTurn) {
            if (this.cardState[idx] === 'up') {
                this.cardState[idx] = 'down';
                this._renderCard(idx);
            }
        }
        this.flippedThisTurn = [];
    }

    _switchTurn() {
        this.currentPlayer = this.currentPlayer === 0 ? 1 : 0;
        this.flippedThisTurn = [];
        this.turnLocked = false;
        this._updateUI();
    }

    _handleWin(matchResult) {
        const attackerWins = this.currentPlayer === this.attackerIdx;
        // Mark matched cards
        for (const idx of this.flippedThisTurn) {
            if (this.deck[idx].value === matchResult.value) {
                this.cardState[idx] = 'matched';
                this._renderCard(idx);
            }
        }
        this._updateUI();

        // Show win message
        const winner = this.players[this.currentPlayer];
        const role = this.currentPlayer === this.attackerIdx ? 'Attacker' : 'Defender';
        const msg = document.createElement('div');
        msg.style.cssText = 'text-align:center; margin-top:8px;';
        msg.innerHTML = `
            <div style="font-size:20px; font-weight:bold; color:#e94560;">
                ${this._esc(winner.name)} (${role}) matched ${matchResult.count}× ${matchResult.value}!
            </div>
        `;
        this.container.appendChild(msg);

        setTimeout(() => {
            if (!this._destroyed) this.end({ attackerWins, tie: false });
        }, 2000);
    }

    // ── Rendering ────────────────────────────────────────

    _renderCard(idx) {
        const el = this._cardEls[idx];
        const state = this.cardState[idx];

        if (state === 'down') {
            el.className = 'hc-card hc-card-back';
            el.innerHTML = '<span class="hc-card-inner">🂠</span>';
            el.style.borderColor = '';
            el.style.boxShadow = '';
        } else if (state === 'up') {
            const card = this.deck[idx];
            const color = this.suitColors[card.suit];
            el.className = 'hc-card hc-card-face';
            el.innerHTML = `<span class="hc-card-inner" style="color:${color}; font-size:11px; font-weight:bold; line-height:1.1;">${card.value}<br>${card.suit}</span>`;
            el.style.borderColor = '#ffd700';
            el.style.boxShadow = '0 0 6px rgba(255,215,0,0.4)';
        } else if (state === 'matched') {
            const card = this.deck[idx];
            const color = this.suitColors[card.suit];
            el.className = 'hc-card hc-card-matched';
            el.innerHTML = `<span class="hc-card-inner" style="color:${color}; font-size:11px; font-weight:bold; line-height:1.1;">${card.value}<br>${card.suit}</span>`;
            el.style.borderColor = '#2ecc71';
            el.style.boxShadow = '0 0 8px rgba(46,204,113,0.5)';
        }
    }

    _updateUI() {
        // Turn indicator
        const player = this.players[this.currentPlayer];
        const role = this.currentPlayer === this.attackerIdx ? 'Attacker' : 'Defender';
        const roleColor = this.currentPlayer === this.attackerIdx ? '#e94560' : '#4ecdc4';
        this._turnBar.innerHTML = `
            <span style="font-size:24px;">${player.icon || '🎮'}</span>
            <span style="font-size:14px; font-weight:600; color:#e0e0e0;">${this._esc(player.name)}</span>
            <span style="font-size:11px; color:${roleColor}; font-weight:700; text-transform:uppercase;">${role}</span>
        `;

        // Status counters
        const maxFlips0 = this.playerFlips[0];
        const maxFlips1 = this.playerFlips[1];
        const flipped0 = this.currentPlayer === 0 ? this.flippedThisTurn.length : 0;
        const flipped1 = this.currentPlayer === 1 ? this.flippedThisTurn.length : 0;
        const role0 = 0 === this.attackerIdx ? 'Attacker' : 'Defender';
        const role1 = 1 === this.attackerIdx ? 'Attacker' : 'Defender';
        const color0 = 0 === this.attackerIdx ? '#e94560' : '#4ecdc4';
        const color1 = 1 === this.attackerIdx ? '#e94560' : '#4ecdc4';
        const active0 = this.currentPlayer === 0 ? 'font-weight:bold; color:#e0e0e0;' : 'color:#666;';
        const active1 = this.currentPlayer === 1 ? 'font-weight:bold; color:#e0e0e0;' : 'color:#666;';

        this._statusBar.innerHTML = `
            <div style="display:flex; align-items:center; gap:6px; ${active0}">
                <span style="font-size:18px;">${this.players[0].icon || '⚔️'}</span>
                <span style="font-size:12px;">${this._esc(this.players[0].name)}</span>
                <span style="font-size:11px; color:${color0};">Cards: ${flipped0}/${maxFlips0}</span>
                <span style="font-size:10px; color:#888;">(match ${this.playerTarget[0]})</span>
            </div>
            <div style="display:flex; align-items:center; gap:6px; ${active1}">
                <span style="font-size:18px;">${this.players[1].icon || '🛡️'}</span>
                <span style="font-size:12px;">${this._esc(this.players[1].name)}</span>
                <span style="font-size:11px; color:${color1};">Cards: ${flipped1}/${maxFlips1}</span>
                <span style="font-size:10px; color:#888;">(match ${this.playerTarget[1]})</span>
            </div>
        `;
    }

    // ── Helpers ───────────────────────────────────────────

    _shuffle(arr) {
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
    }

    _esc(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
