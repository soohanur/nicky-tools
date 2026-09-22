"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import AppBar from "@/components/layout/AppBar";
import Rail from "@/components/layout/Rail";
import ColumnMapperModal from "@/components/dashboard/ColumnMapperModal";
import NotificationPanel from "@/components/dashboard/NotificationPanel";
import { useAuth } from "@/hooks/useAuth";
import { JobProvider, useJob } from "@/hooks/useJob";
import { jobSocket } from "@/lib/ws";

// Dashboard chrome: icon rail + app bar + content, plus the overlays every
// dashboard page shares (notification panel, column mapper, scrim).
// Gated client-side: no token -> /login.
export default function Shell({ title, children }) {
  const router = useRouter();
  const { ready, isAuthenticated } = useAuth();

  useEffect(() => {
    if (ready && !isAuthenticated) router.replace("/login/");
  }, [ready, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) jobSocket.connect();
  }, [isAuthenticated]);

  if (!ready || !isAuthenticated) return null;

  return (
    <JobProvider>
      <ShellInner title={title}>{children}</ShellInner>
    </JobProvider>
  );
}

function ShellInner({ title, children }) {
  const [notifOpen, setNotifOpen] = useState(false);
  const { mapper, cancelMapping, confirmMapping } = useJob();

  const scrimShown = notifOpen || mapper.open;
  const closeAll = () => {
    setNotifOpen(false);
    if (mapper.open) cancelMapping();
  };

  return (
    <div className="app">
      <Rail />
      <div className="main">
        <AppBar title={title} onOpenNotifications={() => setNotifOpen(true)} />
        <div className="content">{children}</div>
      </div>

      <ColumnMapperModal
        open={mapper.open}
        filename={mapper.filename}
        headers={mapper.headers}
        sheet={mapper.sheet}
        headerRow={mapper.headerRow}
        onConfirm={confirmMapping}
        onCancel={cancelMapping}
      />
      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
      <div className={`scrim${scrimShown ? " show" : ""}`} onClick={closeAll} aria-hidden="true" />
    </div>
  );
}
