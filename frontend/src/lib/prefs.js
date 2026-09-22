// Notification preferences from the Settings page (localStorage, per browser).
import { createStore, readJson, writeJson } from "@/lib/store";

const KEY = "scraply-prefs";

export const DEFAULT_PREFS = {
  completionSound: true,
  browserNotifications: true,
  autoExport: false,
};

const store = createStore(null);

export function getPrefs() {
  if (store.get() !== null) return store.get();
  const saved = typeof window === "undefined" ? null : readJson(KEY, null);
  return store.hydrate({ ...DEFAULT_PREFS, ...(saved || {}) });
}

export function setPref(key, value) {
  const next = { ...getPrefs(), [key]: value };
  writeJson(KEY, next);
  store.set(next);
}

export const subscribe = store.subscribe;
