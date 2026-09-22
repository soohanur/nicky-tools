// *** The single HTTP transport for the whole frontend. ***
// This is the ONLY module allowed to call `fetch`. Components, hooks and the
// api.js modules must call apiFetch / apiFetchAuthed - never fetch directly.
import { clearSession, getToken } from "@/lib/auth";
import { env } from "@/lib/env";

export class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function messageFrom(data, status) {
  const detail = data?.detail ?? data?.error;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(data?.errors) && data.errors.length) {
    const e = data.errors[0];
    return e?.msg ? `${e.loc?.slice(-1)[0] ?? "field"}: ${e.msg}` : "Validation error";
  }
  if (status === 401) return "Session expired. Please sign in again.";
  return "Something went wrong. Please try again.";
}

async function request(path, { method = "GET", body, form, token, headers, blob } = {}) {
  const init = {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers || {}),
    },
  };

  if (form) {
    // FormData or URLSearchParams: let the browser set the content type.
    init.body = form;
  } else if (body != null) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(`${env.apiUrl}${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection.");
  }

  if (res.status === 401 && token) {
    // Token rejected: drop the session; the dashboard guard sends the user to /login.
    clearSession();
  }

  if (res.status === 204) return undefined;

  if (blob) {
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new ApiError(res.status, messageFrom(data, res.status), data);
    }
    return res.blob();
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(data, res.status), data);
  return data;
}

// Unauthenticated request.
export function apiFetch(path, opts) {
  return request(path, opts);
}

// Authenticated request - injects the bearer token from the auth store.
export function apiFetchAuthed(path, opts) {
  return request(path, { ...(opts || {}), token: getToken() });
}
