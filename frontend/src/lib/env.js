// Central access to environment variables - keeps `process.env` lookups in one
// place so the rest of the app imports named constants.

// Backend origin without the /api/v1 suffix. Empty = same origin (production,
// where nginx proxies /api/ to FastAPI).
const apiOrigin = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

export const env = {
  apiOrigin,
  apiUrl: `${apiOrigin}/api/v1`,
};

export const isProd = process.env.NODE_ENV === "production";

// ws(s)://host/api/v1/ws - derived at call time because window is browser-only.
export function wsUrl(token) {
  const base = apiOrigin || (typeof window !== "undefined" ? window.location.origin : "");
  const ws = base.replace(/^https:/, "wss:").replace(/^http:/, "ws:");
  return `${ws}/api/v1/ws?token=${encodeURIComponent(token)}`;
}
