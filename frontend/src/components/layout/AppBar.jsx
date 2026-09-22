"use client";

import Icon from "@/components/ui/Icon";
import { useJob } from "@/hooks/useJob";
import { useNotifications } from "@/hooks/useNotifications";

// Sticky top bar: page title, job-wide Export / Cancel, notification bell.
export default function AppBar({ title, onOpenNotifications }) {
  const { flags, exportResult, cancel } = useJob();
  const { unread } = useNotifications();

  return (
    <header className="appbar">
      <div>
        <h1>{title}</h1>
      </div>
      <div className="right">
        <button type="button" className="btn btn-ghost" disabled={!flags.canExport} onClick={exportResult}>
          <Icon name="download" />
          Export
        </button>
        <button type="button" className="btn btn-danger" disabled={!flags.canCancel} onClick={cancel}>
          <Icon name="stop" />
          Cancel
        </button>
        <button
          type="button"
          className="icon-btn"
          aria-label="Notifications"
          onClick={onOpenNotifications}
        >
          <Icon name="bell" />
          {unread > 0 && <span className="dot">{unread > 99 ? "99+" : unread}</span>}
        </button>
      </div>
    </header>
  );
}
