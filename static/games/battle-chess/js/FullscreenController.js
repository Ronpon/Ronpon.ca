/** Fullscreen belongs to the whole game so dialogs remain visible above the board. */
export class FullscreenController {
    constructor() {
        this.surface = document.getElementById('game-surface');
        this.button = document.getElementById('toggle-fullscreen');
        this.message = document.getElementById('fullscreen-message');
        this.boardContainer = document.getElementById('canvas-container');
        this.active = false;
        this._expanded = false;
        this._pending = false;
        this._frame = null;
        this._onToggle = () => this.toggle();
        this._onChange = () => this._setActive(this._nativeActive() || this._expanded);
        this._onResize = () => this._scheduleLayout();
        this._onKeyDown = event => {
            if (event.key === 'Escape' && this.active) {
                if (this._expanded) event.preventDefault();
                this.exit();
            }
        };
    }

    init() {
        this.button.addEventListener('click', this._onToggle);
        document.addEventListener('fullscreenchange', this._onChange);
        document.addEventListener('webkitfullscreenchange', this._onChange);
        document.addEventListener('keydown', this._onKeyDown);
        window.addEventListener('resize', this._onResize);
        window.visualViewport?.addEventListener('resize', this._onResize);
        this._resizeObserver = new ResizeObserver(this._onResize);
        this._resizeObserver.observe(this.surface);
        this._observeChrome();
        // Online play inserts its connection/action bar beside the board after init.
        this._mutationObserver = new MutationObserver(() => {
            this._observeChrome();
            this._scheduleLayout();
        });
        this._mutationObserver.observe(this.surface, { childList: true });
    }

    _nativeActive() {
        return (document.fullscreenElement || document.webkitFullscreenElement) === this.surface;
    }

    _observeChrome() {
        for (const child of this.surface.children) {
            if (child !== this.boardContainer && child.id !== 'overlay-container') {
                this._resizeObserver.observe(child);
            }
        }
    }

    async toggle() {
        if (this._pending) return;
        if (this.active) return this.exit();
        this._pending = true;
        this.button.disabled = true;
        this._showMessage('');
        try {
            const request = this.surface.requestFullscreen || this.surface.webkitRequestFullscreen;
            if (request) {
                await request.call(this.surface);
                this._setActive(this._nativeActive());
            } else {
                this._expanded = true;
                this._setActive(true);
                this._showMessage('Expanded view. Use Exit full screen or press Escape to return.');
            }
        } catch {
            this._expanded = false;
            this._setActive(this._nativeActive());
            this._showMessage('Full screen could not open. Please try the Full screen button again.');
        } finally {
            this._pending = false;
            this.button.disabled = false;
        }
    }

    async exit() {
        if (this._pending) return;
        this._pending = true;
        this.button.disabled = true;
        try {
            this._expanded = false;
            if (this._nativeActive()) {
                const exit = document.exitFullscreen || document.webkitExitFullscreen;
                await exit.call(document);
            }
            this._setActive(false);
            this._showMessage('');
        } catch {
            this._setActive(this._nativeActive());
            this._showMessage('Full screen could not close. Press Escape or try Exit full screen again.');
        } finally {
            this._pending = false;
            this.button.disabled = false;
        }
    }

    _setActive(active) {
        const wasActive = this.active;
        if (active && !wasActive) this._scrollPosition = { x: window.scrollX, y: window.scrollY };
        this.active = active;
        this.surface.classList.toggle('fullscreen-active', active);
        document.documentElement.classList.toggle('battle-fullscreen', active);
        document.body.classList.toggle('battle-fullscreen', active);
        this.button.textContent = active ? 'Exit full screen' : 'Full screen';
        this.button.setAttribute('aria-pressed', String(active));
        this.button.title = active ? 'Exit full screen (Escape)' : 'Open the game in full screen';
        if (active) {
            this._scheduleLayout();
        } else {
            this.surface.style.removeProperty('--fullscreen-board-size');
            this.surface.style.removeProperty('--fullscreen-overlay-top');
            this._showMessage('');
            if (wasActive && this._scrollPosition) {
                const position = this._scrollPosition;
                requestAnimationFrame(() => {
                    if (!this.active) window.scrollTo(position.x, position.y);
                });
            }
        }
    }

    _showMessage(text) {
        this.message.textContent = text;
        this.message.hidden = !text;
        this._scheduleLayout();
    }

    _scheduleLayout() {
        if (!this.active || this._frame !== null) return;
        this._frame = requestAnimationFrame(() => {
            this._frame = null;
            if (this.active) this._layout();
        });
    }

    _layout() {
        const styles = getComputedStyle(this.surface);
        const chrome = [...this.surface.children].filter(child => {
            if (child === this.boardContainer) return false;
            const childStyles = getComputedStyle(child);
            return childStyles.display !== 'none' && !['absolute', 'fixed'].includes(childStyles.position);
        });
        const width = this.surface.clientWidth - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight);
        const height = this.surface.clientHeight - parseFloat(styles.paddingTop) - parseFloat(styles.paddingBottom)
            - chrome.reduce((total, child) => total + child.getBoundingClientRect().height, 0)
            - (parseFloat(styles.rowGap) || 0) * chrome.length;
        const size = `${Math.max(1, Math.floor(Math.min(width, height)))}px`;
        if (this.surface.style.getPropertyValue('--fullscreen-board-size') !== size) {
            this.surface.style.setProperty('--fullscreen-board-size', size);
        }
        const toolbar = this.surface.querySelector('.board-appearance');
        const top = Math.ceil(toolbar.getBoundingClientRect().bottom - this.surface.getBoundingClientRect().top
            + (parseFloat(styles.rowGap) || 0));
        this.surface.style.setProperty('--fullscreen-overlay-top', `${top}px`);
    }

    destroy() {
        this.button.removeEventListener('click', this._onToggle);
        document.removeEventListener('fullscreenchange', this._onChange);
        document.removeEventListener('webkitfullscreenchange', this._onChange);
        document.removeEventListener('keydown', this._onKeyDown);
        window.removeEventListener('resize', this._onResize);
        window.visualViewport?.removeEventListener('resize', this._onResize);
        this._resizeObserver.disconnect();
        this._mutationObserver.disconnect();
        if (this._frame !== null) cancelAnimationFrame(this._frame);
        this._frame = null;
        this.exit();
    }
}
