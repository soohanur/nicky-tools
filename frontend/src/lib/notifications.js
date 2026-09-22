// Notification store: persisted to localStorage, observable via subscribe().
// Shape: { id, type: 'success'|'error'|'warning'|'info', title, message, timestamp, read, jobUuid }
const KEY = "scraply-notifications";
const MAX = 100;

let items = [];
let loaded = false;
const listeners = new Set();

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) items = JSON.parse(raw).map((n) => ({ ...n, timestamp: new Date(n.timestamp) }));
  } catch {
    items = [];
  }
}

function persist() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* ignore */
  }
}

function emit() {
  listeners.forEach((fn) => fn(items));
}

function commit(next) {
  items = next;
  persist();
  emit();
}

export function getNotifications() {
  load();
  return items;
}

export function unreadCount() {
  load();
  return items.filter((n) => !n.read).length;
}

export function subscribe(fn) {
  load();
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function addNotification({ type = "info", title, message, jobUuid }) {
  load();
  const n = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    title,
    message,
    jobUuid,
    timestamp: new Date(),
    read: false,
  };
  commit([n, ...items].slice(0, MAX));
  return n.id;
}

export function markRead(id) {
  load();
  commit(items.map((n) => (n.id === id ? { ...n, read: true } : n)));
}

export function markAllRead() {
  load();
  commit(items.map((n) => ({ ...n, read: true })));
}

export function removeNotification(id) {
  load();
  commit(items.filter((n) => n.id !== id));
}

export function clearNotifications() {
  commit([]);
}
