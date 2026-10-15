/**
 * Blue Margin — Centralized Reactive State Singleton
 * docs/js/store.js
 * 
 * Enforces single source of truth across all 6 workspaces.
 * Communicates via custom events: window.dispatchEvent(new CustomEvent('bm:...'))
 */

class StateStore {
  constructor() {
    this.state = {
      manifest: null,
      current: null,
      selectedSymbol: 'ng',
      selectedContract: 'MCX:NATURALGAS26OCTFUT',
      selectedWorkspace: 'pulse',
      isLiveConnected: false,
      liveState: {
        ltp: 309.20,
        chg: 1.45,
        chgPct: 0.47,
        spread: 0.10,
        bids: [],
        asks: []
      },
      cachedData: new Map()
    };
    this.listeners = new Map();
  }

  // Subscribe to state change events
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.listeners.get(event).delete(callback);
  }

  // Emit event to subscribers and dispatch to DOM window
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(cb => {
        try { cb(data); } catch (e) { console.error(`Error in listener for ${event}:`, e); }
      });
    }
    window.dispatchEvent(new CustomEvent(`bm:${event}`, { detail: data }));
  }

  // Update state slice and trigger event
  set(slice, data) {
    this.state[slice] = data;
    this.emit(`change:${slice}`, data);
  }

  get(slice) {
    return this.state[slice];
  }

  // Async cached JSON fetcher
  async fetchJson(url) {
    if (this.state.cachedData.has(url)) {
      return this.state.cachedData.get(url);
    }
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status} on ${url}`);
      const data = await resp.json();
      this.state.cachedData.set(url, data);
      return data;
    } catch (err) {
      console.warn(`[Store] Failed to load ${url}:`, err);
      return null;
    }
  }
}

export const store = new StateStore();
window.__bmStore = store;
