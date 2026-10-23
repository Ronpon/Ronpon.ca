import { GameEvent, MinigameMode, MinigameAdvantage } from '../Constants.js';

/**
 * Multi-step setup wizard overlay.
 * Screens: Player Count → Solo Settings → Player Profiles → Minigame Selection → Rules
 * Emits SETUP_COMPLETE with the full game config when done.
 */
export class SetupWizard {
    constructor(overlayContainer, eventBus, minigameRegistry) {
        this.container = overlayContainer;
        this.eventBus = eventBus;
        this.minigameRegistry = minigameRegistry; // { id, name, thumbnail } list

        this.panel = null;
        this.config = {
            playerCount: 2,
            chessDifficulty: 'medium',
            aiDifficulty: 'medium',
            players: [
                { name: '', icon: null, color: 'w' },
                { name: '', icon: null, color: 'b' }
            ],
            selectedMinigames: [],
            minigameMode: MinigameMode.RANDOM,
            minigameAdvantage: MinigameAdvantage.ATTACKER,
            attackerLosesPiece: false
        };
        this._humanColor = 'w';
        this._soloProfile = null;
        this._localProfiles = this.config.players.map(player => ({ ...player }));

        // Available player icons (emoji-based for now)
        this.availableIcons = [
            '⚔️', '👑', '🏰', '🐴', '⚡', '🔥',
            '🌟', '💎', '🎯', '🛡️', '🦁', '🐉',
            '🦅', '🐺', '🎭', '🌙'
        ];
    }

    show() {
        this._showPlayerCount();
    }

    // ── Screen 1: Player Count ───────────────────────────
    _showPlayerCount() {
        this._render(`
            <h2>How Many Players?</h2>
            <div class="setup-player-count">
                <button class="btn btn-primary setup-count-btn" id="btn-1p">
                    <span class="count-num">1</span>
                    <span class="count-label">Player</span>
                    <span class="count-sub">vs AI</span>
                </button>
                <button class="btn btn-primary setup-count-btn" id="btn-2p">
                    <span class="count-num">2</span>
                    <span class="count-label">Players</span>
                    <span class="count-sub">Local Multiplayer</span>
                </button>
            </div>
        `);

        this.panel.querySelector('#btn-1p').addEventListener('click', () => {
            if (this.config.playerCount !== 1) {
                this._localProfiles = this.config.players.map(player => ({ ...player }));
                if (!this._soloProfile) {
                    const humanIndex = this._humanColor === 'w' ? 0 : 1;
                    this._soloProfile = { ...this.config.players[humanIndex] };
                }
            }
            this.config.playerCount = 1;
            this._syncSoloPlayers();
            this._showSoloSettings();
        });
        this.panel.querySelector('#btn-2p').addEventListener('click', () => {
            const profiles = this.config.playerCount === 1 ? this._localProfiles : this.config.players;
            this.config.players = profiles.map((player, idx) => ({
                name: player.name,
                icon: player.icon,
                color: idx === 0 ? 'w' : 'b'
            }));
            this.config.playerCount = 2;
            this._showPlayerProfiles();
        });
    }

    _syncSoloPlayers() {
        const human = this._soloProfile || { name: '', icon: null };
        this.config.players = ['w', 'b'].map(color => color === this._humanColor ? {
            name: human.name,
            icon: human.icon,
            color
        } : {
            name: 'Computer',
            icon: '🤖',
            color,
            isAI: true
        });
    }

    _showSoloSettings() {
        this._render(`
            <h2>Play Against AI</h2>
            <div class="setup-solo-settings">
                <div class="setup-setting">
                    <label for="chess-difficulty">Chess difficulty</label>
                    <p id="chess-difficulty-help">Controls the computer's chess strategy and planning on the board.</p>
                    <select id="chess-difficulty" aria-describedby="chess-difficulty-help">
                        <option value="easy">Easy</option>
                        <option value="medium">Medium</option>
                        <option value="hard">Hard</option>
                    </select>
                </div>
                <div class="setup-setting">
                    <label for="ai-difficulty">Battle AI difficulty</label>
                    <p id="ai-difficulty-help">Controls the computer's reflexes, accuracy, and memory in battle minigames.</p>
                    <select id="ai-difficulty" aria-describedby="ai-difficulty-help">
                        <option value="easy">Easy</option>
                        <option value="medium">Medium</option>
                        <option value="hard">Hard</option>
                    </select>
                </div>
                <div class="setup-setting">
                    <label for="human-color">Your side</label>
                    <select id="human-color">
                        <option value="w">White — You move first</option>
                        <option value="b">Black — Computer moves first</option>
                    </select>
                </div>
            </div>
            <div class="setup-actions">
                <button class="btn" id="btn-back-solo">Back</button>
                <button class="btn btn-primary" id="btn-next-solo">Continue</button>
            </div>
        `);

        const chessDifficulty = this.panel.querySelector('#chess-difficulty');
        const aiDifficulty = this.panel.querySelector('#ai-difficulty');
        const humanColor = this.panel.querySelector('#human-color');
        chessDifficulty.value = this.config.chessDifficulty;
        aiDifficulty.value = this.config.aiDifficulty;
        humanColor.value = this._humanColor;
        chessDifficulty.addEventListener('change', () => {
            this.config.chessDifficulty = chessDifficulty.value;
        });
        aiDifficulty.addEventListener('change', () => {
            this.config.aiDifficulty = aiDifficulty.value;
        });
        humanColor.addEventListener('change', () => {
            this._humanColor = humanColor.value;
            this._syncSoloPlayers();
        });
        this.panel.querySelector('#btn-back-solo').addEventListener('click', () => {
            this._showPlayerCount();
        });
        this.panel.querySelector('#btn-next-solo').addEventListener('click', () => {
            this._showPlayerProfiles();
        });
    }

    // ── Screen 2: Player Profiles ────────────────────────
    _showPlayerProfiles() {
        const buildPlayerColumn = (idx) => {
            const player = this.config.players[idx];
            const defaultName = this.config.playerCount === 1 ? 'You' : `Player ${idx + 1}`;
            const colorLabel = idx === 0 ? 'White' : 'Black';
            if (player.isAI) {
                return `
                    <div class="setup-profile setup-computer-profile" data-player="${idx}">
                        <h3>${colorLabel}</h3>
                        <div class="setup-computer-icon" aria-hidden="true">🤖</div>
                        <p class="setup-computer-name">Computer</p>
                        <p class="setup-computer-note">AI opponent</p>
                    </div>
                `;
            }
            return `
                <div class="setup-profile" data-player="${idx}">
                    <h3>${colorLabel}</h3>
                    <input type="text" class="setup-name-input" data-player="${idx}"
                           aria-label="${colorLabel} player name" placeholder="${defaultName}" maxlength="16">
                    <div class="setup-icon-label">Choose Icon</div>
                    <div class="setup-icon-grid" data-player="${idx}">
                        ${this.availableIcons.map((icon, i) => `
                            <button class="setup-icon-btn" data-player="${idx}" data-icon="${icon}" data-index="${i}"
                                    title="${icon}">${icon}</button>
                        `).join('')}
                    </div>
                </div>
            `;
        };

        this._render(`
            <h2>Player Setup</h2>
            <div class="setup-profiles-row">
                ${buildPlayerColumn(0)}
                <div class="setup-divider"></div>
                ${buildPlayerColumn(1)}
            </div>
            <div class="setup-actions">
                <button class="btn" id="btn-back-count">Back</button>
                <button class="btn btn-primary" id="btn-next-profiles">Continue</button>
            </div>
        `);

        this.panel.querySelectorAll('.setup-name-input').forEach(input => {
            const pIdx = Number(input.dataset.player);
            // Assign names as values so saved profile text is never interpreted as HTML.
            input.value = this.config.players[pIdx].name;
        });
        this.config.players.forEach((player, idx) => {
            if (!player.icon) player.icon = idx === 0 ? '⚔️' : '🛡️';
        });

        this.panel.querySelectorAll('.setup-icon-btn').forEach(btn => {
            const pIdx = Number(btn.dataset.player);
            const icon = btn.dataset.icon;
            btn.classList.toggle('selected', this.config.players[pIdx].icon === icon);
            btn.addEventListener('click', () => {
                this.config.players[pIdx].icon = icon;

                // Highlight selected icon for this player
                this.panel.querySelectorAll(`.setup-icon-btn[data-player="${pIdx}"]`).forEach(b => {
                    b.classList.toggle('selected', b.dataset.icon === icon);
                });
            });
        });

        this.panel.querySelector('#btn-back-count').addEventListener('click', () => {
            this._saveProfiles();
            if (this.config.playerCount === 1) this._showSoloSettings();
            else this._showPlayerCount();
        });

        this.panel.querySelector('#btn-next-profiles').addEventListener('click', () => {
            this._saveProfiles(true);
            this._showMinigameSelection();
        });
    }

    _saveProfiles(useDefaults = false) {
        this.panel.querySelectorAll('.setup-name-input').forEach(input => {
            const pIdx = Number(input.dataset.player);
            const fallback = this.config.playerCount === 1 ? 'You' : `Player ${pIdx + 1}`;
            this.config.players[pIdx].name = input.value.trim() || (useDefaults ? fallback : '');
        });
        if (this.config.playerCount === 1) {
            this._soloProfile = { ...this.config.players.find(player => !player.isAI) };
        } else {
            this._localProfiles = this.config.players.map(player => ({ ...player }));
        }
    }

    // ── Screen 3: Minigame Selection ─────────────────────
    _showMinigameSelection() {
        const games = this.minigameRegistry || [];
        const hasGames = games.length > 0;

        // Group games by category
        let gameListHTML = '';
        if (hasGames) {
            const grouped = {};
            for (const g of games) {
                const cat = g.category || 'Other';
                if (!grouped[cat]) grouped[cat] = [];
                grouped[cat].push(g);
            }
            for (const [cat, catGames] of Object.entries(grouped)) {
                gameListHTML += `<div class="setup-mg-category">
                    <div class="setup-mg-category-title">${cat}</div>
                    ${catGames.map(g => `
                        <label class="setup-minigame-item">
                            <input type="checkbox" class="setup-mg-check" data-id="${g.id}"
                                   ${this.config.selectedMinigames.includes(g.id) ? 'checked' : ''}>
                            <span class="setup-mg-thumb">${g.thumbnail || '🎮'}</span>
                            <span class="setup-mg-name">${g.name}</span>
                        </label>
                    `).join('')}
                </div>`;
            }
        } else {
            gameListHTML = `<p class="setup-no-games">No minigames available yet.<br>The game will play as standard chess.</p>`;
        }

        this._render(`
            <h2>Minigame Selection</h2>
            ${hasGames ? `
                <label class="setup-minigame-item">
                    <input type="checkbox" id="select-all-minigames">
                    <span class="setup-mg-name">Select all minigames</span>
                </label>
            ` : ''}
            <div class="setup-minigame-list">
                ${gameListHTML}
            </div>
            ${hasGames ? `
                <div class="setup-mode-section">
                    <label class="setup-mode-label">Selection Mode</label>
                    <div class="setup-mode-options" id="mode-options">
                        <button class="btn setup-mode-btn" data-mode="${MinigameMode.RANDOM}">Random</button>
                        <button class="btn setup-mode-btn" data-mode="${MinigameMode.ATTACKER_CHOICE}">Attacker's Choice</button>
                        <button class="btn setup-mode-btn" data-mode="${MinigameMode.DEFENDER_CHOICE}">Defender's Choice</button>
                        <button class="btn setup-mode-btn" data-mode="${MinigameMode.SET_ORDER}">Set Order</button>
                    </div>
                </div>
            ` : ''}
            <div class="setup-actions">
                <button class="btn" id="btn-back-profiles">Back</button>
                <button class="btn btn-primary" id="btn-next-minigames">
                    ${hasGames ? 'Continue' : 'Start Game'}
                </button>
            </div>
        `);

        if (hasGames) {
            const modeContainer = this.panel.querySelector('#mode-options');
            const modeButtons = this.panel.querySelectorAll('.setup-mode-btn');
            const gameCheckboxes = [...this.panel.querySelectorAll('.setup-mg-check')];
            const selectAll = this.panel.querySelector('#select-all-minigames');
            let selectedMode = this.config.minigameMode;
            modeButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === selectedMode));

            // Mode toggle disabled until 2+ games selected
            const updateModeState = () => {
                const checked = gameCheckboxes.filter(checkbox => checkbox.checked);
                const disabled = checked.length <= 1;
                modeContainer.classList.toggle('disabled', disabled);
                modeButtons.forEach(b => b.disabled = disabled);
                selectAll.checked = checked.length === gameCheckboxes.length;
                selectAll.indeterminate = checked.length > 0 && checked.length < gameCheckboxes.length;
                this.config.selectedMinigames = checked.map(checkbox => checkbox.dataset.id);
            };

            modeButtons.forEach(btn => {
                btn.addEventListener('click', () => {
                    if (btn.disabled) return;
                    selectedMode = btn.dataset.mode;
                    this.config.minigameMode = selectedMode;
                    modeButtons.forEach(b => b.classList.toggle('active', b === btn));
                });
            });

            gameCheckboxes.forEach(cb => {
                cb.addEventListener('change', updateModeState);
            });
            selectAll.addEventListener('change', () => {
                gameCheckboxes.forEach(checkbox => checkbox.checked = selectAll.checked);
                updateModeState();
            });

            updateModeState();

            this.panel.querySelector('#btn-next-minigames').addEventListener('click', () => {
                const checked = [...this.panel.querySelectorAll('.setup-mg-check:checked')];
                this.config.selectedMinigames = checked.map(c => c.dataset.id);
                this.config.minigameMode = selectedMode;

                if (this.config.selectedMinigames.length > 0) {
                    this._showMinigameAdvantage();
                } else {
                    this._finish();
                }
            });
        } else {
            // No minigames — "Start Game" goes straight to game
            this.panel.querySelector('#btn-next-minigames').addEventListener('click', () => {
                this.config.selectedMinigames = [];
                this._finish();
            });
        }

        this.panel.querySelector('#btn-back-profiles').addEventListener('click', () => {
            this._showPlayerProfiles();
        });
    }

    // ── Screen 4: Minigame Advantage ──────────────────────
    _showMinigameAdvantage() {
        this._render(`
            <h2>Minigame Advantage</h2>
            <p class="setup-rule-desc">
                Some minigames give a small starting advantage to one side. Who should receive it?
            </p>
            <div class="setup-rule-options setup-advantage-options">
                <button class="btn setup-rule-btn" id="adv-attacker">
                    <span class="rule-icon">⚔️</span>
                    <span class="rule-title">Attacker</span>
                    <span class="rule-sub">Default — attacker gets the edge</span>
                </button>
                <button class="btn setup-rule-btn" id="adv-defender">
                    <span class="rule-icon">🛡️</span>
                    <span class="rule-title">Defender</span>
                    <span class="rule-sub">Defender gets the edge instead</span>
                </button>
                <button class="btn setup-rule-btn" id="adv-none">
                    <span class="rule-icon">⚖️</span>
                    <span class="rule-title">None</span>
                    <span class="rule-sub">No advantage — perfectly even</span>
                </button>
            </div>
            <div class="setup-actions">
                <button class="btn" id="btn-back-minigames-adv">Back</button>
            </div>
        `);

        this.panel.querySelector('#adv-attacker').addEventListener('click', () => {
            this.config.minigameAdvantage = MinigameAdvantage.ATTACKER;
            this._showAttackerLossRule();
        });

        this.panel.querySelector('#adv-defender').addEventListener('click', () => {
            this.config.minigameAdvantage = MinigameAdvantage.DEFENDER;
            this._showAttackerLossRule();
        });

        this.panel.querySelector('#adv-none').addEventListener('click', () => {
            this.config.minigameAdvantage = MinigameAdvantage.NONE;
            this._showAttackerLossRule();
        });

        this.panel.querySelector('#btn-back-minigames-adv').addEventListener('click', () => {
            this._showMinigameSelection();
        });
    }

    // ── Screen 5: Attacker Loss Rule ─────────────────────
    _showAttackerLossRule() {
        this._render(`
            <h2>Attacker Loss Rule</h2>
            <p class="setup-rule-desc">
                When the attacking player <strong>loses</strong> a minigame, does their piece get removed from the board?
            </p>
            <div class="setup-rule-options">
                <button class="btn setup-rule-btn" id="rule-yes">
                    <span class="rule-icon">✕</span>
                    <span class="rule-title">Yes</span>
                    <span class="rule-sub">Attacker's piece is removed</span>
                </button>
                <button class="btn setup-rule-btn" id="rule-no">
                    <span class="rule-icon">↩</span>
                    <span class="rule-title">No</span>
                    <span class="rule-sub">Both pieces stay — nothing happens</span>
                </button>
            </div>
            <div class="setup-actions">
                <button class="btn" id="btn-back-minigames">Back</button>
            </div>
        `);

        this.panel.querySelector('#rule-yes').addEventListener('click', () => {
            this.config.attackerLosesPiece = true;
            this._finish();
        });

        this.panel.querySelector('#rule-no').addEventListener('click', () => {
            this.config.attackerLosesPiece = false;
            this._finish();
        });

        this.panel.querySelector('#btn-back-minigames').addEventListener('click', () => {
            this._showMinigameAdvantage();
        });
    }

    // ── Finish & emit config ─────────────────────────────
    _finish() {
        this.hide();
        this.eventBus.emit(GameEvent.SETUP_COMPLETE, { ...this.config });
    }

    // ── DOM helpers ──────────────────────────────────────
    _render(html) {
        this.panel = document.createElement('div');
        this.panel.className = 'overlay-panel setup-panel';
        this.panel.innerHTML = html;

        this.container.innerHTML = '';
        this.container.appendChild(this.panel);
        this.container.classList.add('active');
    }

    hide() {
        this.container.classList.remove('active');
        this.container.innerHTML = '';
        this.panel = null;
    }
}
