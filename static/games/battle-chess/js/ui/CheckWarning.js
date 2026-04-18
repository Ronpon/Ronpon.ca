/**
 * Warning popup shown when a player in check attempts a capture that will
 * trigger a minigame. Losing the minigame while in check = checkmate.
 *
 * "Remember: If you fail to take this piece, you will be in checkmate."
 * Buttons: "Fight" | "Back"
 * Checkbox: "Don't show this again this game"
 */
export class CheckWarning {
    constructor(overlayContainer) {
        this.container = overlayContainer;
        this.suppressed = false; // "don't show again" flag, resets each game
    }

    /**
     * Show the warning popup. Returns a promise that resolves to true (fight)
     * or false (back). Resolves immediately with true if suppressed.
     */
    show() {
        if (this.suppressed) return Promise.resolve(true);

        return new Promise((resolve) => {
            const panel = document.createElement('div');
            panel.className = 'overlay-panel check-warning-panel';
            panel.innerHTML = `
                <h2>⚠️ Warning</h2>
                <p class="check-warning-text">
                    Remember: If you fail to take this piece, you will be in checkmate.
                </p>
                <label class="check-warning-suppress">
                    <input type="checkbox" class="check-warning-checkbox">
                    Don't show this again this game
                </label>
                <div class="check-warning-actions">
                    <button class="btn btn-primary" id="check-fight-btn">Fight</button>
                    <button class="btn" id="check-back-btn">Back</button>
                </div>
            `;

            this.container.innerHTML = '';
            this.container.appendChild(panel);
            this.container.classList.add('active');

            const cleanup = (result) => {
                const cb = panel.querySelector('.check-warning-checkbox');
                if (cb.checked) this.suppressed = true;
                this.container.classList.remove('active');
                this.container.innerHTML = '';
                resolve(result);
            };

            panel.querySelector('#check-fight-btn').addEventListener('click', () => cleanup(true));
            panel.querySelector('#check-back-btn').addEventListener('click', () => cleanup(false));
        });
    }

    /** Reset suppression (called at start of each new game). */
    reset() {
        this.suppressed = false;
    }
}
