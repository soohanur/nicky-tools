"use client";

import Icon from "@/components/ui/Icon";

// Inline dismissible message. type: "err" | "ok"
export default function Alert({ type = "err", children, onClose }) {
  if (!children) return null;
  return (
    <div className={`alert ${type}`} role="alert">
      <Icon name={type === "ok" ? "checkc" : "x"} />
      <span className="grow">{children}</span>
      {onClose && (
        <button type="button" className="x" aria-label="Dismiss" onClick={onClose}>
          <Icon name="x" />
        </button>
      )}
    </div>
  );
}
