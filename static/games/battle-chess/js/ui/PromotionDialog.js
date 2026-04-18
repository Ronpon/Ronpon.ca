/**
 * HTML overlay popup that lets the player choose a promotion piece.
 * Appears when a pawn reaches the 8th/1st rank.
 */
export class PromotionDialog {
    constructor(overlayContainer, inputHandler, eventBus) {
        this.container = overlayContainer;
        this.inputHandler = inputHandler;
        this.eventBus = eventBus;
        this.panel = null;

        this.eventBus.on('promotionRequired', (data) => this.show(data));
    }

    show({ from, to }) {
        const color = from[1] === '7' ? 'w' : 'b'; // white promotes from rank 7→8, black from rank 2→1

        const pieces = [
            { type: 'q', label: 'Queen',  char: color === 'w' ? '\u265B' : '\u265B' },
            { type: 'r', label: 'Rook',   char: color === 'w' ? '\u265C' : '\u265C' },
            { type: 'b', label: 'Bishop', char: color === 'w' ? '\u265D' : '\u265D' },
            { type: 'n', label: 'Knight', char: color === 'w' ? '\u265E' : '\u265E' }
        ];

        this.panel = document.createElement('div');
        this.panel.className = 'overlay-panel';
        this.panel.innerHTML = `
            <h2>Promote Pawn</h2>
            <div class="promotion-choices">
                ${pieces.map(p => `
                    <button class="promotion-btn" data-piece="${p.type}" title="${p.label}">
                        <span class="promotion-icon ${color === 'w' ? 'white-piece' : 'black-piece'}">${p.char}</span>
                        <span class="promotion-label">${p.label}</span>
                    </button>
                `).join('')}
            </div>
            <button class="btn" id="promotion-cancel">Cancel</button>
        `;

        // Wire up buttons
        this.panel.querySelectorAll('.promotion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const piece = btn.dataset.piece;
                this.hide();
                this.inputHandler.resolvePromotion(piece);
            });
        });

        this.panel.querySelector('#promotion-cancel').addEventListener('click', () => {
            this.hide();
            this.inputHandler.cancelPromotion();
        });

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
