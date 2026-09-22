// Display helpers shared by tables, stats and notifications.

export function formatNumber(n) {
  return Number(n || 0).toLocaleString("en-US");
}

export function formatBytes(bytes) {
  const b = Number(bytes || 0);
  if (b === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(b) / Math.log(k)), sizes.length - 1);
  return `${(b / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
}

// "Jun 07, 2026" in Amsterdam time.
export function formatDate(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleDateString("en-US", {
    timeZone: "Europe/Amsterdam",
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

// "Jun 07, 2026, 14:32"
export function formatDateTime(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("en-US", {
    timeZone: "Europe/Amsterdam",
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// "just now", "2 min ago", "1 hr ago", "3 days ago"
export function timeAgo(value) {
  const t = value instanceof Date ? value.getTime() : new Date(value).getTime();
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} day${d === 1 ? "" : "s"} ago`;
  return formatDate(t);
}

export function capitalize(s) {
  return s ? s[0].toUpperCase() + s.slice(1) : "";
}

// Strip the "<uuid>_<timestamp>_" storage prefix from a stored filename.
export function displayName(stored) {
  if (!stored) return "";
  return stored.replace(/^[0-9a-f-]{36}_\d{8}_\d{6}_/i, "");
}

export function stripExt(name) {
  return (name || "").replace(/\.[^/.]+$/, "");
}

// Trigger a browser download for a Blob.
export function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
