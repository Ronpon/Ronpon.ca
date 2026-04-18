/**
 * Simple publish/subscribe event bus for decoupled communication.
 * All modules communicate through this instead of direct references.
 */
export class EventBus {
    constructor() {
        this._listeners = {};
    }

    /**
     * Subscribe to an event. Returns an unsubscribe function.
     */
    on(event, callback) {
        if (!this._listeners[event]) {
            this._listeners[event] = [];
        }
        this._listeners[event].push(callback);
        return () => this.off(event, callback);
    }

    /**
     * Unsubscribe from an event.
     */
    off(event, callback) {
        if (!this._listeners[event]) return;
        this._listeners[event] = this._listeners[event].filter(cb => cb !== callback);
    }

    /**
     * Emit an event with optional data.
     */
    emit(event, data) {
        if (!this._listeners[event]) return;
        for (const cb of this._listeners[event]) {
            cb(data);
        }
    }
}
