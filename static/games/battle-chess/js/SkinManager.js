/**
 * Manages skin packs (board colors + piece images).
 *
 * Default skin uses Unicode chess characters rendered on canvas.
 * Custom skins provide image files (PNG/SVG) for each piece.
 *
 * To add a skin: create a folder in assets/skins/ with a manifest.json.
 * See assets/skins/default/manifest.json for the format.
 */
export class SkinManager {
    constructor() {
        this.currentSkin = null;
        this.currentSkinId = null;
        this.pieceImages = {};
    }

    /**
     * Load a skin by ID (folder name under assets/skins/).
     * 'default' uses the built-in Unicode piece renderer.
     */
    async loadSkin(skinId) {
        let manifest;
        const basePath = `assets/skins/${skinId}`;

        if (skinId === 'default') {
            manifest = DEFAULT_MANIFEST;
        } else {
            const resp = await fetch(`${basePath}/manifest.json`);
            if (!resp.ok) {
                console.warn(`[SkinManager] Failed to load skin "${skinId}", falling back to default.`);
                manifest = DEFAULT_MANIFEST;
                skinId = 'default';
            } else {
                manifest = await resp.json();
            }
        }

        // Load piece images if this skin provides them
        this.pieceImages = {};
        if (manifest.pieceStyle === 'images' && manifest.pieces) {
            await this._loadPieceImages(basePath, manifest.pieces);
        }

        this.currentSkin = manifest;
        this.currentSkinId = skinId;
        console.log(`[SkinManager] Loaded skin: ${manifest.name}`);
        return manifest;
    }

    getBoardColors() {
        return this.currentSkin.boardColors;
    }

    /**
     * Draw a piece on the canvas context.
     * Uses loaded images if available, otherwise falls back to Unicode rendering.
     */
    drawPiece(ctx, type, color, x, y, size) {
        const key = color + type.toUpperCase(); // e.g. 'wK', 'bQ'
        if (this.pieceImages[key]) {
            ctx.drawImage(this.pieceImages[key], x, y, size, size);
            return;
        }
        this._drawDefaultPiece(ctx, type, color, x, y, size);
    }

    // ── Image loading for custom skins ────────────────────

    async _loadPieceImages(basePath, pieceFileMap) {
        const entries = Object.entries(pieceFileMap);
        await Promise.all(entries.map(([key, file]) => new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                this.pieceImages[key] = img;
                resolve();
            };
            img.onerror = () => {
                console.warn(`[SkinManager] Missing piece image: ${basePath}/${file}`);
                resolve(); // Graceful fallback — Unicode will be used for this piece
            };
            img.src = `${basePath}/${file}`;
        })));
    }

    // ── Default Unicode piece renderer ────────────────────

    _drawDefaultPiece(ctx, type, color, x, y, size) {
        const CHARS = {
            k: '\u265A', q: '\u265B', r: '\u265C',
            b: '\u265D', n: '\u265E', p: '\u265F'
        };
        const char = CHARS[type];
        if (!char) return;

        const cx = x + size / 2;
        const cy = y + size / 2;
        const fontSize = Math.round(size * 0.82);

        ctx.save();
        ctx.font = `${fontSize}px serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Drop shadow for depth
        ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        ctx.shadowBlur = 3;
        ctx.shadowOffsetX = 1;
        ctx.shadowOffsetY = 2;

        // Outline (contrasting color for visibility on any square)
        ctx.lineWidth = size * 0.025;
        ctx.lineJoin = 'round';
        ctx.strokeStyle = color === 'w' ? '#000' : '#ccc';
        ctx.strokeText(char, cx, cy);

        // Fill (no shadow to avoid doubling)
        ctx.shadowColor = 'transparent';
        ctx.fillStyle = color === 'w' ? '#fff' : '#222';
        ctx.fillText(char, cx, cy);

        ctx.restore();
    }
}

// ── Default skin definition (no external files needed) ──

const DEFAULT_MANIFEST = Object.freeze({
    name: 'Classic',
    author: 'Battle Chess',
    description: 'Classic wooden board with standard pieces',
    boardColors: Object.freeze({
        light: '#F0D9B5',
        dark: '#B58863',
        selected: 'rgba(255, 255, 0, 0.5)',
        validMove: 'rgba(0, 0, 0, 0.25)',
        lastMove: 'rgba(255, 255, 0, 0.2)',
        check: 'rgba(255, 0, 0, 0.5)'
    }),
    pieceStyle: 'default'
});
