"use client";

import { useCallback, useSyncExternalStore } from "react";

import { authApi } from "@/lib/api";
import {
  SERVER_SNAPSHOT,
  clearSession,
  getSession,
  setSession,
  setUser as storeUser,
  subscribe,
} from "@/lib/auth";
import { jobSocket } from "@/lib/ws";

const getServerSnapshot = () => SERVER_SNAPSHOT;

// Reactive view of the auth store. `ready` is false during prerender and the
// hydration pass, so guards never redirect before localStorage has been read.
export function useAuth() {
  const session = useSyncExternalStore(subscribe, getSession, getServerSnapshot);

  const login = useCallback(async (identity, password) => {
    const { access_token: token } = await authApi.login(identity, password);
    setSession(token, null);
    const user = await authApi.me().catch(() => null);
    storeUser(user);
    jobSocket.connect();
    return user;
  }, []);

  const register = useCallback((fields) => authApi.register(fields), []);

  const logout = useCallback(() => {
    jobSocket.disconnect();
    clearSession();
  }, []);

  return { ...session, isAuthenticated: !!session.token, login, register, logout };
}
