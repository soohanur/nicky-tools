// Typed-ish wrappers over the FastAPI backend (see backend/app/domains/*).
// Every call goes through api-client.js.
import { apiFetch, apiFetchAuthed } from "@/lib/api-client";

export const authApi = {
  // OAuth2 password form: the backend accepts username OR email in `username`.
  login(identity, password) {
    const form = new URLSearchParams();
    form.append("username", identity);
    form.append("password", password);
    return apiFetch("/auth/login", { method: "POST", form });
  },
  register({ email, username, password, adminKey }) {
    return apiFetch("/auth/register", {
      method: "POST",
      body: { email, username, password, admin_key: adminKey },
    });
  },
  me() {
    return apiFetchAuthed("/auth/me");
  },
};

export const jobsApi = {
  create({ name, description = "CompanyInfo scraping job", config = {} }) {
    return apiFetchAuthed("/jobs", {
      method: "POST",
      body: { tool_type: "scraply", name, description, priority: "normal", config },
    });
  },
  list(params = {}) {
    const q = new URLSearchParams();
    if (params.status) q.set("status_filter", params.status);
    if (params.page) q.set("page", params.page);
    if (params.pageSize) q.set("page_size", params.pageSize);
    const qs = q.toString();
    return apiFetchAuthed(`/jobs${qs ? `?${qs}` : ""}`);
  },
  get(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}`);
  },
  update(uuid, patch) {
    return apiFetchAuthed(`/jobs/${uuid}`, { method: "PATCH", body: patch });
  },
  start(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}/start`, { method: "POST" });
  },
  pause(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}/pause`, { method: "POST" });
  },
  resume(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}/resume`, { method: "POST" });
  },
  cancel(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}/cancel`, { method: "POST" });
  },
  retry(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}/retry`, { method: "POST" });
  },
  remove(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}`, { method: "DELETE" });
  },
  logs(uuid, limit = 100) {
    return apiFetchAuthed(`/jobs/${uuid}/logs?limit=${limit}`);
  },
  download(uuid) {
    return apiFetchAuthed(`/jobs/${uuid}/download`, { blob: true });
  },
};

export const filesApi = {
  upload(file, jobUuid) {
    const form = new FormData();
    form.append("file", file);
    return apiFetchAuthed(`/files/upload?job_uuid=${encodeURIComponent(jobUuid)}`, {
      method: "POST",
      form,
    });
  },
  inputs() {
    return apiFetchAuthed("/files/inputs");
  },
  outputs() {
    return apiFetchAuthed("/files/outputs");
  },
  download(filename) {
    return apiFetchAuthed(`/files/download/${encodeURIComponent(filename)}`, { blob: true });
  },
  remove(filename, type = "input") {
    return apiFetchAuthed(`/files/${encodeURIComponent(filename)}?file_type=${type}`, {
      method: "DELETE",
    });
  },
  headers(filename) {
    return apiFetchAuthed(`/files/csv-headers/${encodeURIComponent(filename)}`);
  },
};

export const systemApi = {
  health() {
    return apiFetchAuthed("/system/health");
  },
  stats() {
    return apiFetchAuthed("/system/stats");
  },
  workerConfig() {
    return apiFetchAuthed("/system/config/workers");
  },
  setWorkers(maxWorkers) {
    return apiFetchAuthed("/system/config/workers", {
      method: "POST",
      body: { max_workers: maxWorkers },
    });
  },
};
