"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";

// Auth pages: a signed-in visitor goes straight to the dashboard.
export default function AuthLayout({ children }) {
  const router = useRouter();
  const { ready, isAuthenticated } = useAuth();

  useEffect(() => {
    if (ready && isAuthenticated) router.replace("/");
  }, [ready, isAuthenticated, router]);

  if (!ready || isAuthenticated) return null;
  return children;
}
