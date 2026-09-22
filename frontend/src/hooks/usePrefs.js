"use client";

import { useSyncExternalStore } from "react";

import { DEFAULT_PREFS, getPrefs, setPref, subscribe } from "@/lib/prefs";

const getServerSnapshot = () => DEFAULT_PREFS;

export function usePrefs() {
  const prefs = useSyncExternalStore(subscribe, getPrefs, getServerSnapshot);
  return { prefs, setPref };
}
