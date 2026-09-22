"use client";

import Icon from "@/components/ui/Icon";
import Switch from "@/components/ui/Switch";
import { usePrefs } from "@/hooks/usePrefs";

const ROWS = [
  { key: "completionSound", title: "Completion sound", note: "Play beeps when a job finishes" },
  { key: "browserNotifications", title: "Browser notifications", note: "Desktop alert on status change" },
  { key: "autoExport", title: "Auto-export on finish", note: "Download enriched CSV automatically" },
];

export default function NotificationsCard() {
  const { prefs, setPref } = usePrefs();

  const toggle = (key, on) => {
    setPref(key, on);
    if (key === "browserNotifications" && on && "Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  };

  return (
    <div className="card">
      <div className="card-head">
        <h2>Notifications</h2>
      </div>
      {ROWS.map((r, i) => (
        <div
          key={r.key}
          className="row between"
          style={{ padding: "14px 0", borderBottom: i < ROWS.length - 1 ? "1px solid var(--line-2)" : "none" }}
        >
          <div>
            <b>{r.title}</b>
            <div className="dim small">{r.note}</div>
          </div>
          <Switch checked={prefs[r.key]} onChange={(on) => toggle(r.key, on)} label={r.title} />
        </div>
      ))}
      <div className="empty mt16" style={{ padding: 24 }}>
        <div className="ei">
          <Icon name="cog" />
        </div>
        <h3>More settings under development</h3>
        <p>Proxy pools, retry policy and schedules are coming soon.</p>
      </div>
    </div>
  );
}
