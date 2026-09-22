"use client";

import { useSyncExternalStore } from "react";

import {
  addNotification,
  getNotifications,
  markAllRead,
  markRead,
  removeNotification,
  subscribe,
} from "@/lib/notifications";

const EMPTY = [];
const getServerSnapshot = () => EMPTY;

// Reactive view of the notification store (see lib/notifications.js).
export function useNotifications() {
  const items = useSyncExternalStore(subscribe, getNotifications, getServerSnapshot);
  return {
    items,
    unread: items.filter((n) => !n.read).length,
    add: addNotification,
    markRead,
    markAllRead,
    remove: removeNotification,
  };
}
