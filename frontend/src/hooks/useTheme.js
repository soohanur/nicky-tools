"use client";

import { useSyncExternalStore } from "react";

import { getTheme, setTheme, subscribe } from "@/lib/theme";

const getServerSnapshot = () => "light";

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getTheme, getServerSnapshot);
  return { theme, setTheme, isDark: theme === "dark" };
}
