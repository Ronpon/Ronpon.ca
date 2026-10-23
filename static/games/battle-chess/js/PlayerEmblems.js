// One crest collection for profile selection, battle panels, and canvas avatars.
// Keep the established values so existing player configurations remain compatible.
export const PLAYER_EMBLEMS = Object.freeze([
    { value: '⚔️', label: 'Blades', path: 'M5 4l8 6-3 3L5 4ZM27 4l-8 6 3 3 5-9ZM12 12l11 12M20 12 9 24M6 20l6 6M20 20l6 6M5 28l4-4M27 28l-4-4' },
    { value: '👑', label: 'Crown', path: 'M5 24h22M7 21 4 10l7 5 5-10 5 10 7-5-3 11ZM9 27h14M12 21v-3M20 21v-3' },
    { value: '🏰', label: 'Citadel', path: 'M7 27V14H5V6h5v5h4V6h4v5h4V6h5v8h-2v13ZM12 27v-7a4 4 0 0 1 8 0v7M8 16h16M5 27h22' },
    { value: '🐴', label: 'Knight', path: 'M7 28h19M9 24c0-6 3-9 9-13l-5 2-5-3 7-5 1-3 6 4c4 5 5 11 3 18ZM19 8h.1M8 10l2 4 3-1M12 24h13' },
    { value: '⚡', label: 'Storm', path: 'M18 3 7 18h8l-1 11 11-17h-8l1-9ZM5 8l3 1M24 23l3 1M5 25l2-2M25 5l2-2' },
    { value: '🔥', label: 'Ember', path: 'M18 3c2 8-4 8-1 14 2-1 4-4 4-6 9 9 6 18-5 18C5 29 2 19 10 11c-1 5 1 7 3 8-2-7 4-10 5-16ZM16 20c-5 4-5 7 0 9 5-2 5-5 0-9Z' },
    { value: '🌟', label: 'Dawn', path: 'm16 5 3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1 3-7ZM16 1v1M16 30v1M1 16h2M29 16h2M5 5l2 2M25 25l2 2M5 27l2-2M25 7l2-2' },
    { value: '💎', label: 'Crystal', path: 'm5 11 6-6h10l6 6-11 17L5 11ZM5 11h22M11 5l-1 6 6 17 6-17-1-6M10 11l6-6 6 6' },
    { value: '🎯', label: 'Archer', path: 'M25 16a9 9 0 1 1-9-9M21 16a5 5 0 1 1-5-5M16 16 28 4M23 4h5v5M16 3v2M3 16h2M16 27v2' },
    { value: '🛡️', label: 'Warden', path: 'm16 3 11 4v9c0 7-6 11-11 14C11 27 5 23 5 16V7l11-4ZM16 7v18M9 11h14M10 15l6 5 6-5' },
    { value: '🦁', label: 'Lion', path: 'm16 3 6 2 5 6-1 9-4 7-6 2-6-2-4-7-1-9 5-6 6-2ZM11 9l-2 3 2 8 5 5 5-5 2-8-2-3M11 14l3 1M21 14l-3 1M14 19h4l-2 2-2-2ZM16 21v3' },
    { value: '🐉', label: 'Dragon', path: 'm11 5 6 1 3-3 1 6 6 4-7 3-2-2-4 4c-2 3 0 6 4 6 3 0 5-2 6-4 1 7-5 11-11 8C4 25 4 18 9 13l4-4-2-4ZM13 8l4 3M21 11h.1M9 14l-5-2 2 7M18 24l1-5M12 23l-3 4' },
    { value: '🦅', label: 'Eagle', path: 'm16 7 4-3 3 2-4 4v4l10-7-4 9-8 3 6 8-7-4-7 4 6-8-8-3-4-9 10 7V9l3-2ZM8 12l4 5M24 12l-4 5M14 27l2-4 2 4' },
    { value: '🐺', label: 'Wolf', path: 'm6 4 8 5h4l8-5-1 13-4 8-5 4-5-4-4-8L6 4ZM8 8l5 6-4 1M24 8l-5 6 4 1M12 19l4-2 4 2-4 5-4-5ZM16 24v4' },
    { value: '🎭', label: 'Masque', path: 'M5 8c7 4 15 4 22 0v7c0 7-6 13-11 15C11 28 5 22 5 15V8ZM9 15l5 2-4 1-1-3ZM23 15l-5 2 4 1 1-3ZM12 23c3 2 5 2 8 0M16 4v3M6 3l2 3M26 3l-2 3' },
    { value: '🌙', label: 'Moon', path: 'M23 5a12 12 0 1 0 4 18A12 12 0 0 1 23 5ZM25 7v6M22 10h6M12 5v3M10.5 6.5h3' }
].map(emblem => Object.freeze(emblem)));

const AUTOMATON = Object.freeze({ value: '🤖', label: 'Automaton', path: 'M10 8V5h12v3M8 10l-3 4v12h22V14l-3-4ZM9 15h14M11 19h2M19 19h2M11 24h10M16 2v3M8 12h16M2 16v6M30 16v6' });
const TROPHY = Object.freeze({ value: '🏆', label: 'Champion', path: 'M10 4h12v10a6 6 0 0 1-12 0V4ZM10 7H5v4c0 4 2 6 6 6M22 7h5v4c0 4-2 6-6 6M16 20v6M10 28h12M12 26h8' });
const byValue = new Map([...PLAYER_EMBLEMS, AUTOMATON, TROPHY].map(emblem => [emblem.value, emblem]));
const paths = new Map();

export function getPlayerEmblem(value) {
    return byValue.get(value) || PLAYER_EMBLEMS[0];
}

function escapeAttribute(value) {
    return String(value).replace(/[&"<>']/g, character => ({
        '&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;', "'": '&#39;'
    })[character]);
}

export function playerEmblemMarkup(value, className = 'player-emblem') {
    const emblem = getPlayerEmblem(value);
    const classes = className === 'player-emblem' ? className : `player-emblem ${className}`;
    return `<svg class="${escapeAttribute(classes)}" data-icon="${emblem.value}" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="${emblem.path}"></path></svg>`;
}

/** Draw the same crest on the existing canvas without changing player config. */
export function drawPlayerEmblem(ctx, value, x, y, size, color = '#ead9b8') {
    const emblem = getPlayerEmblem(value);
    // Older canvas implementations can retain the established text representation.
    if (typeof Path2D === 'undefined') {
        ctx.fillText(emblem.value, x, y);
        return;
    }
    if (!paths.has(emblem.value)) paths.set(emblem.value, new Path2D(emblem.path));
    ctx.save();
    ctx.translate(x - size / 2, y - size / 2);
    ctx.scale(size / 32, size / 32);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke(paths.get(emblem.value));
    ctx.restore();
}
