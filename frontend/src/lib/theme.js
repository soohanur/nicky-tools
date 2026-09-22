// Light / dark theme, persisted per browser and mirrored onto <html data-theme>.
import { createStore, readJson, writeJson } from "@/lib/store";

const KEY = "scraply-theme";

const store = createStore(null);

export function getTheme() {
  if (store.get() !== null) return store.get();
  const saved = typeof window === "undefined" ? null : readJson(KEY, null);
  return store.hydrate(saved === "dark" ? "dark" : "light");
}

export function setTheme(next) {
  const theme = next === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  writeJson(KEY, theme);
  store.set(theme);
}

export const subscribe = store.subscribe;

// Inline script for <head>: applies the saved theme before first paint.
export const THEME_SCRIPT = `(function(){try{var t=JSON.parse(localStorage.getItem("${KEY}"));if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t);}catch(e){}})();`;
