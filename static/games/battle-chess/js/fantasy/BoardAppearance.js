// Presentation preferences stay local, including when playing an online opponent.
export class BoardAppearance {
    constructor(board) {
        this.board = board;
        this.fantasyCanvas = document.getElementById('fantasy-canvas');
        this.fantasyButton = document.getElementById('view-fantasy');
        this.elvenButton = document.getElementById('view-elven');
        this.classicButton = document.getElementById('view-classic');
        this.status = document.getElementById('board-view-status');
        this.controls = document.getElementById('fantasy-controls');
    }

    async init() {
        this.fantasyCanvas.addEventListener('boardcamerachange', event => {
            this.controls.querySelector('[data-view="top"]').setAttribute('aria-pressed', String(event.detail.topView));
        });
        this.fantasyButton.addEventListener('click', () => this.setStyle('fantasy'));
        this.elvenButton.addEventListener('click', () => this.setStyle('elven'));
        this.classicButton.addEventListener('click', () => this.setStyle('classic'));
        this.controls.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
            this.board.fantasy?.setView(button.dataset.view);
            this.controls.querySelector('[data-view="top"]').setAttribute('aria-pressed', String(this.board.fantasy.elevation > 1.4));
        }));
        document.getElementById('export-runeforge').addEventListener('click', async event => {
            const button = event.currentTarget;
            button.disabled = true;
            this.status.textContent = 'Preparing your GLB file...';
            try {
                const theme = this.board.fantasy.theme;
                const binary = await this.board.fantasy.exportAssets();
                const url = URL.createObjectURL(new Blob([binary], { type: 'model/gltf-binary' }));
                const link = document.createElement('a');
                link.href = url;
                link.download = theme === 'elven' ? 'sylvan-court-chess-set.glb' : 'runeforge-chess-set.glb';
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 10000);
                this.status.textContent = '3D set exported as GLB';
            } catch (error) {
                console.warn('[Runeforge] Export failed:', error);
                this.status.textContent = 'Export failed. Please try again.';
            } finally { button.disabled = false; }
        });
        let preferred = 'fantasy';
        try { preferred = localStorage.getItem('battle-chess-board-style') || preferred; } catch { /* Private browsing. */ }
        await this.setStyle(['classic', 'elven'].includes(preferred) ? preferred : 'fantasy');
    }

    async setStyle(style) {
        // Serialize initialization so rapid toggles cannot create multiple WebGL contexts.
        this.requestedStyle = style;
        if (style !== 'classic' && !this.board.fantasy) {
            this.status.textContent = 'Preparing the 3D arena...';
            this.fantasyButton.disabled = true;
            this.elvenButton.disabled = true;
            try {
                this.loading ||= import('./FantasyBoard.js').then(({ FantasyBoard }) => {
                    this.board.fantasy = new FantasyBoard(this.fantasyCanvas, message => this.fallback(message), this.requestedStyle === 'elven' ? 'elven' : 'runeforge');
                });
                await this.loading;
            } catch (error) {
                console.warn('[Runeforge] 3D unavailable:', error);
                this.loading = null;
                this.fallback('3D is unavailable in this browser. Classic view is ready to play.');
                return;
            } finally { this.fantasyButton.disabled = false; this.elvenButton.disabled = false; }
        }
        if (style !== this.requestedStyle) return;
        const fantasy = style !== 'classic', elven = style === 'elven';
        if (fantasy) this.board.fantasy.setTheme(elven ? 'elven' : 'runeforge');
        this.board.fantasyActive = fantasy;
        this.board.canvas.hidden = fantasy;
        this.fantasyCanvas.hidden = !fantasy;
        this.controls.hidden = !fantasy;
        document.getElementById('fantasy-caption').hidden = !fantasy;
        document.body.classList.toggle('runeforge-active', fantasy);
        document.body.classList.toggle('elven-active', elven);
        document.body.dataset.boardTheme = elven ? 'elven' : (fantasy ? 'runeforge' : 'classic');
        this.fantasyButton.setAttribute('aria-pressed', String(style === 'fantasy'));
        this.elvenButton.setAttribute('aria-pressed', String(elven));
        this.classicButton.setAttribute('aria-pressed', String(!fantasy));
        this.status.textContent = elven ? 'Where moonlight meets silverwood' : (fantasy ? 'Forged above the molten depths' : 'Classic wooden board');
        const title = document.querySelector('.forge-header h1');
        title.textContent = elven ? 'Sylvan Court' : (fantasy ? 'Runeforge' : 'Battle Chess');
        const subtitle = document.createElement('span');
        subtitle.textContent = elven ? 'Sunleaf & Moonveil' : (fantasy ? 'Ivory & Obsidian' : 'The classic collection');
        title.appendChild(subtitle);
        document.getElementById('faction-white').textContent = elven ? 'SUNLEAF COURT' : 'DAWN GUARD';
        document.getElementById('faction-black').textContent = elven ? 'MOONVEIL COURT' : 'DUSK COURT';
        this.fantasyCanvas.setAttribute('aria-label', `${elven ? 'Sylvan Court' : 'Runeforge'} 3D chessboard. Click or tap a piece, then a highlighted square to move. Hold and drag to rotate and tilt.`);
        try { localStorage.setItem('battle-chess-board-style', style); } catch { /* Optional preference. */ }
        if (fantasy) this.board.fantasy.resize();
        this.board.render();
    }

    fallback(message) {
        this.setStyle('classic');
        if (this.board.fantasy?.contextLost) { this.fantasyButton.disabled = true; this.elvenButton.disabled = true; }
        this.status.textContent = message;
    }
}
