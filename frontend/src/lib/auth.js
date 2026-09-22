// JWT + current user persisted in localStorage (static export: no server session).
// Components read auth through the useAuth hook; api-client reads the token here.
import { createStore, readJson, writeJson } from "@/lib/store";

const TOKEN_KEY = "scraply-token";
const USER_KEY = "scraply-user";

// Snapshot before localStorage is read (server render / first client paint).
export const SERVER_SNAPSHOT = { ready: false, token: null, user: null };

function fromStorage() {
  if (typeof window === "undefined") return SERVER_SNAPSHOT;
  return { ready: true, token: readJson(TOKEN_KEY, null), user: readJson(USER_KEY, null) };
}

const store = createStore(null);

// Lazily hydrated so the module can load during prerender.
export function getSession() {
  if (store.get() !== null) return store.get();
  return store.hydrate(fromStorage());
}

export const subscribe = store.subscribe;

export function getToken() {
  return getSession().token;
}

export function getUser() {
  return getSession().user;
}

export function setSession(token, user) {
  writeJson(TOKEN_KEY, token);
  writeJson(USER_KEY, user);
  store.set({ ready: true, token, user });
}

export function setUser(user) {
  writeJson(USER_KEY, user);
  store.set((s) => ({ ...(s || SERVER_SNAPSHOT), ready: true, user }));
}

export function clearSession() {
  writeJson(TOKEN_KEY, null);
  writeJson(USER_KEY, null);
  store.set({ ready: true, token: null, user: null });
}

export function isAuthenticated() {
  return !!getToken();
}
