/**
 * Popup overlay for Attacker's Choice / Defender's Choice minigame mode.
 * Shows available minigames with thumbnails; the choosing player picks one.
 */
export class MinigameChooser {
    constructor(overlayContainer, eventBus) {
        this.container = overlayContainer;
        this.eventBus = eventBus;

        this.eventBus.on('minigameChoose', (ctx) => this._show(ctx));
    }

    _show({ playerName, games, onChoice }) {
        const panel = document.createElement('div');
        panel.className = 'overlay-panel mg-chooser-panel';
        panel.innerHTML = `
            <h2>${this._escapeHtml(playerName)} Chooses Game</h2>
            <div class="mg-chooser-grid">
                ${games.map(g => `
                    <button class="mg-chooser-btn" data-id="${g.id}" title="${this._escapeHtml(g.name)}">
                        <span class="mg-chooser-thumb">${g.thumbnail || '🎮'}</span>
                        <span class="mg-chooser-name">${this._escapeHtml(g.name)}</span>
                    </button>
                `).join('')}
            </div>
        `;

        this.container.innerHTML = '';
        this.container.appendChild(panel);
        this.container.classList.add('active');

        panel.querySelectorAll('.mg-chooser-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.dataset.id;
                this._hide();
                onChoice(id);
            });
        });
    }

    _hide() {
        this.container.classList.remove('active');
        this.container.innerHTML = '';
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
