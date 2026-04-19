import { BaseMinigame } from './BaseMinigame.js';

/**
 * Highest Card — luck-based card minigame.
 *
 * 52 cards face-down in 4 rows of 13. Each player clicks a card to choose.
 * Attacker picks first. Cards are revealed; highest card wins.
 * Advantage: the advantaged side wins ties.
 *
 * Card values: 2–10, J=11, Q=12, K=13, A=14.
 * Suit tiebreak (only if values tie AND advantage is 'none' — shouldn't happen
 * since 'none' means ties cause a rematch): Spades > Hearts > Diamonds > Clubs.
 */
export class HighestCard extends BaseMinigame {
    constructor() {
        super();
        this.id = 'highest-card';
        this.name = 'Highest Card';
        this.thumbnail = '🃏';
        this.category = 'Luck';
        this.description = 'Pick a card — highest card wins!';
        this.controls = {
            player1: 'Click a card',
            player2: 'Click a card'
        };
    }

    init(container, config) {
        super.init(container, config);

        // Dynamic description
        if (this.advantage === 'attacker') {
            this.description = 'Pick a card — highest card wins! The attacker wins ties.';
        } else if (this.advantage === 'defender') {
            this.description = 'Pick a card — highest card wins! The defender wins ties.';
        } else {
            this.description = 'Pick a card — highest card wins! Ties cause a rematch.';
        }

        // Build and shuffle deck
        this.suits = ['♠', '♥', '♦', '♣'];
        this.suitColors = { '♠': '#e0e0e0', '♥': '#e94560', '♦': '#e94560', '♣': '#e0e0e0' };
        this.values = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
        this.valueRank = {};
        this.values.forEach((v, i) => this.valueRank[v] = i + 2);

        this.deck = [];
        for (const suit of this.suits) {
            for (const val of this.values) {
                this.deck.push({ suit, value: val, rank: this.valueRank[val] });
            }
        }
        this._shuffle(this.deck);

        // State
        this.p1Choice = null; // index into deck
        this.p2Choice = null;
        this.phase = 'p1-pick'; // 'p1-pick' | 'p2-pick' | 'reveal-ready' | 'revealed' | 'done'
        // Attacker picks first; attacker is always associated with their role, but
        // P1 is always left, P2 always right. We map attacker to first picker.
        this.attackerIdx = this.attackerColor === 'w' ? 0 : 1;
        this.defenderIdx = this.attackerColor === 'w' ? 1 : 0;
        this.currentPicker = this.attackerIdx; // attacker picks first

        this._onClick = this._onClick.bind(this);
    }

    start() {
        this.container.innerHTML = '';
        this.container.style.display = 'flex';
        this.container.style.flexDirection = 'column';
        this.container.style.alignItems = 'center';
        this.container.style.justifyContent = 'center';
        this.container.style.padding = '16px';
        this.container.style.gap = '12px';
        this.container.style.overflowY = 'auto';

        // Turn indicator
        this._turnLabel = document.createElement('div');
        this._turnLabel.style.cssText = 'font-size:16px; font-weight:bold; color:#e94560; text-align:center; min-height:24px;';
        this.container.appendChild(this._turnLabel);

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
            el.innerHTML = '<img class="hc-card-img" src="Images/Battle%20Chess%20Card%20back.png" alt="card" draggable="false">';
            this._grid.appendChild(el);
            this._cardEls.push(el);
        }

        // Reveal / result area
        this._revealArea = document.createElement('div');
        this._revealArea.style.cssText = 'display:none; flex-direction:column; align-items:center; gap:12px; margin-top:8px;';
        this.container.appendChild(this._revealArea);

        this._grid.addEventListener('click', this._onClick);
        this._updateTurnLabel();
    }

    destroy() {
        if (this._grid) this._grid.removeEventListener('click', this._onClick);
        super.destroy();
    }

    // ── Click handling ───────────────────────────────────

    _onClick(e) {
        const cardEl = e.target.closest('.hc-card');
        if (!cardEl) return;
        const idx = parseInt(cardEl.dataset.index);

        if (this.phase === 'p1-pick' || this.phase === 'p2-pick') {
            const pickerIsP1 = this.currentPicker === 0;
            const otherChoice = pickerIsP1 ? this.p2Choice : this.p1Choice;
            if (idx === otherChoice) return; // can't pick same card

            // Set choice
            if (pickerIsP1) {
                // Clear previous selection
                if (this.p1Choice !== null) this._clearSelection(this.p1Choice);
                this.p1Choice = idx;
                this._markSelection(idx, 0);
            } else {
                if (this.p2Choice !== null) this._clearSelection(this.p2Choice);
                this.p2Choice = idx;
                this._markSelection(idx, 1);
            }

            // Advance phase
            if (this.phase === 'p1-pick') {
                // First pick (attacker) done → defender picks next
                this.currentPicker = this.defenderIdx;
                this.phase = 'p2-pick';
                this._updateTurnLabel();
            } else if (this.phase === 'p2-pick') {
                if (this.p1Choice !== null && this.p2Choice !== null) {
                    this.phase = 'reveal-ready';
                    this._showRevealButton();
                }
            }
        }
    }

    _markSelection(idx, playerIdx) {
        const el = this._cardEls[idx];
        const icon = this.players[playerIdx].icon || (playerIdx === 0 ? '⚔️' : '🛡️');
        el.classList.add('hc-card-selected');
        el.innerHTML = `<span class="hc-card-inner" style="font-size:20px;">${icon}</span>`;
        el.style.borderColor = playerIdx === 0 ? '#4ecdc4' : '#e94560';
        el.style.boxShadow = `0 0 8px ${playerIdx === 0 ? 'rgba(78,205,196,0.5)' : 'rgba(233,69,96,0.5)'}`;
    }

    _clearSelection(idx) {
        const el = this._cardEls[idx];
        el.classList.remove('hc-card-selected');
        el.innerHTML = '<img class="hc-card-img" src="Images/Battle%20Chess%20Card%20back.png" alt="card" draggable="false">';
        el.style.borderColor = '';
        el.style.boxShadow = '';
    }

    _updateTurnLabel() {
        const player = this.players[this.currentPicker];
        const role = this.currentPicker === this.attackerIdx ? 'Attacker' : 'Defender';
        this._turnLabel.textContent = `${player.name} (${role}) — pick a card`;
    }

    _showRevealButton() {
        this._turnLabel.textContent = 'Both players have chosen!';
        // Disable further clicks on grid
        this._grid.style.pointerEvents = 'none';

        this._revealArea.style.display = 'flex';
        this._revealArea.innerHTML = '';
        const btn = document.createElement('button');
        btn.className = 'btn btn-primary';
        btn.textContent = 'Reveal';
        btn.style.fontSize = '18px';
        btn.style.padding = '12px 40px';
        btn.addEventListener('click', () => this._reveal());
        this._revealArea.appendChild(btn);
    }

    _reveal() {
        this.phase = 'revealed';
        const card1 = this.deck[this.p1Choice];
        const card2 = this.deck[this.p2Choice];

        // Build reveal display
        this._grid.style.display = 'none';
        this._revealArea.innerHTML = '';
        this._revealArea.style.display = 'flex';
        this._revealArea.style.flexDirection = 'row';
        this._revealArea.style.gap = '40px';
        this._revealArea.style.justifyContent = 'center';
        this._revealArea.style.alignItems = 'center';
        this._revealArea.style.marginTop = '0';

        const makeCardDisplay = (player, card, playerIdx) => {
            const role = playerIdx === this.attackerIdx ? 'Attacker' : 'Defender';
            const roleColor = playerIdx === this.attackerIdx ? '#e94560' : '#4ecdc4';
            const suitColor = this.suitColors[card.suit];
            const div = document.createElement('div');
            div.style.cssText = 'display:flex; flex-direction:column; align-items:center; gap:8px;';
            div.innerHTML = `
                <div style="font-size:32px;">${player.icon || '🎮'}</div>
                <div style="font-size:14px; font-weight:600; color:#e0e0e0;">${this._esc(player.name)}</div>
                <div style="font-size:11px; color:${roleColor}; font-weight:700; text-transform:uppercase;">${role}</div>
                <div class="hc-reveal-card" style="
                    width:100px; height:140px; background:#f5f5f0; border-radius:8px;
                    display:flex; flex-direction:column; align-items:center; justify-content:center;
                    border:3px solid ${roleColor}; box-shadow:0 0 16px ${roleColor}44;
                    animation: hcFlipIn 0.4s ease-out;
                ">
                    <span style="font-size:36px; font-weight:bold; color:${suitColor};">${card.value}</span>
                    <span style="font-size:28px; color:${suitColor};">${card.suit}</span>
                </div>
            `;
            return div;
        };

        const vs = document.createElement('div');
        vs.style.cssText = 'font-size:28px; font-weight:bold; color:#e94560;';
        vs.textContent = 'VS';

        this._revealArea.appendChild(makeCardDisplay(this.players[0], card1, 0));
        this._revealArea.appendChild(vs);
        this._revealArea.appendChild(makeCardDisplay(this.players[1], card2, 1));

        // Determine winner after a moment
        setTimeout(() => this._determineWinner(card1, card2), 1200);
    }

    _determineWinner(card1, card2) {
        if (this._destroyed) return;

        const resultDiv = document.createElement('div');
        resultDiv.style.cssText = 'text-align:center; margin-top:4px;';

        if (card1.rank === card2.rank) {
            // Tie
            if (this.advantage === 'none') {
                // True tie → rematch
                resultDiv.innerHTML = `<div style="font-size:20px; font-weight:bold; color:#ffd700; margin-bottom:8px;">It's a tie!</div>`;
                this._revealArea.parentNode.insertBefore(resultDiv, this._revealArea.nextSibling);
                setTimeout(() => {
                    if (!this._destroyed) this.end({ attackerWins: false, tie: true });
                }, 1500);
                return;
            }
            // Advantaged player wins ties
            const advantagedIsAttacker = this.advantage === 'attacker';
            const winnerIdx = advantagedIsAttacker ? this.attackerIdx : this.defenderIdx;
            const winner = this.players[winnerIdx];
            const role = winnerIdx === this.attackerIdx ? 'Attacker' : 'Defender';
            resultDiv.innerHTML = `
                <div style="font-size:14px; color:#ffd700; margin-bottom:4px;">Tie! Advantage decides...</div>
                <div style="font-size:20px; font-weight:bold; color:#e94560;">${this._esc(winner.name)} (${role}) wins!</div>
            `;
            this._revealArea.parentNode.insertBefore(resultDiv, this._revealArea.nextSibling);
            setTimeout(() => {
                if (!this._destroyed) this.end({ attackerWins: advantagedIsAttacker, tie: false });
            }, 2000);
        } else {
            const p1Wins = card1.rank > card2.rank;
            const winnerIdx = p1Wins ? 0 : 1;
            const winner = this.players[winnerIdx];
            const role = winnerIdx === this.attackerIdx ? 'Attacker' : 'Defender';
            const attackerWins = winnerIdx === this.attackerIdx;
            resultDiv.innerHTML = `
                <div style="font-size:20px; font-weight:bold; color:#e94560;">${this._esc(winner.name)} (${role}) wins!</div>
            `;
            this._revealArea.parentNode.insertBefore(resultDiv, this._revealArea.nextSibling);
            setTimeout(() => {
                if (!this._destroyed) this.end({ attackerWins, tie: false });
            }, 2000);
        }
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
