/**
 * Lightweight sound manager stub.
 *
 * Plays sounds for game events. Currently no audio files are bundled —
 * drop .mp3/.ogg files into assets/sounds/ and update the SOUNDS map below.
 *
 * Usage:
 *   SoundManager.play('move');
 *   SoundManager.play('capture');
 */
class _SoundManager {
    constructor() {
        this.enabled = true;
        this._cache = new Map();
    }

    /**
     * Map of sound IDs → file paths (relative to project root).
     * Replace null with actual file paths when assets are available.
     */
    _SOUNDS = {
        move: null,       // e.g. 'assets/sounds/move.mp3'
        capture: null,    // e.g. 'assets/sounds/capture.mp3'
        check: null,
        gameOver: null,
        minigameStart: null,
        minigameWin: null,
        minigameLose: null,
        countdown: null
    };

    play(id) {
        if (!this.enabled) return;
        const path = this._SOUNDS[id];
        if (!path) return; // no asset yet — silent stub

        let audio = this._cache.get(id);
        if (!audio) {
            audio = new Audio(path);
            this._cache.set(id, audio);
        }
        audio.currentTime = 0;
        audio.play().catch(() => {}); // ignore autoplay blocks
    }

    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}

export const SoundManager = new _SoundManager();
