// Tiny observable store for browser-persisted values (theme, prefs, session).
// Snapshots are replaced, never mutated, so useSyncExternalStore sees changes.

export function createStore(initial) {
  let state = initial;
  const listeners = new Set();
  return {
    get: () => state,
    // First read of persisted data: assign without notifying (safe inside getSnapshot).
    hydrate(next) {
      if (state === null) state = next;
      return state;
    },
    set(next) {
      state = typeof next === "function" ? next(state) : next;
      listeners.forEach((fn) => fn());
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

export function readJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function writeJson(key, value) {
  try {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable (private mode): value just will not persist */
  }
}
