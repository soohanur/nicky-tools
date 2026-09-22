"use client";

import Icon from "@/components/ui/Icon";
import { useNotifications } from "@/hooks/useNotifications";
import { useToast } from "@/hooks/useToast";
import { timeAgo } from "@/lib/format";

const LOOK = {
  success: { icon: "checkc", color: "ic-green" },
  error: { icon: "x", color: "ic-red" },
  warning: { icon: "clock", color: "ic-amber" },
  info: { icon: "grid", color: "ic-blue" },
};

// Right-hand slide-in panel listing job notifications.
export default function NotificationPanel({ open, onClose }) {
  const { items, markRead, markAllRead, remove } = useNotifications();
  const toast = useToast();

  return (
    <div className={`notif-panel${open ? " open" : ""}`} aria-hidden={!open}>
      <div className="notif-head">
        <h2>Notifications</h2>
        <button
          type="button"
          className="clear"
          onClick={() => {
            markAllRead();
            toast("All marked read");
          }}
        >
          Mark all read
        </button>
        <button type="button" className="x" aria-label="Close" onClick={onClose}>
          <Icon name="x" />
        </button>
      </div>
      <div className="notif-list">
        {items.length === 0 ? (
          <div className="empty">
            <div className="ei">
              <Icon name="bell" />
            </div>
            <h3>No notifications</h3>
            <p>Job updates will show up here.</p>
          </div>
        ) : (
          items.map((n) => {
            const look = LOOK[n.type] || LOOK.info;
            return (
              <div
                key={n.id}
                className={`notif${n.read ? "" : " unread"}`}
                role="button"
                tabIndex={0}
                onClick={() => markRead(n.id)}
                onKeyDown={(e) => e.key === "Enter" && markRead(n.id)}
              >
                <span className={`ni ${look.color}`}>
                  <Icon name={look.icon} />
                </span>
                <div className="grow">
                  <b>{n.title}</b>
                  <p>{n.message}</p>
                  <time>{timeAgo(n.timestamp)}</time>
                </div>
                <button
                  type="button"
                  className="x"
                  aria-label="Remove"
                  title="Remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(n.id);
                  }}
                  style={{
                    border: 0,
                    background: "transparent",
                    color: "var(--ink-3)",
                    width: 28,
                    height: 28,
                    borderRadius: 8,
                    display: "grid",
                    placeItems: "center",
                    alignSelf: "flex-start",
                  }}
                >
                  <Icon name="x" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
