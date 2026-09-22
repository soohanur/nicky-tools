// WebSocket client for live job updates (backend: app/domains/jobs/websocket.py).
// Messages fan out as window events so any component can listen:
//   job-status-change  { jobUuid, status, data }
//   job-progress       { jobUuid, progress, data }
//   job-log            { jobUuid, data }
//   job-error          { jobUuid, data }
import { getToken } from "@/lib/auth";
import { wsUrl } from "@/lib/env";
import { addNotification } from "@/lib/notifications";

const MAX_RECONNECT = 5;
const HEARTBEAT_MS = 30000;

class JobSocket {
  ws = null;
  attempts = 0;
  heartbeat = null;
  connecting = false;
  subscribed = new Set();

  connect() {
    if (typeof window === "undefined") return;
    if (this.ws?.readyState === WebSocket.OPEN || this.connecting) return;
    const token = getToken();
    if (!token) return;

    this.connecting = true;
    try {
      this.ws = new WebSocket(wsUrl(token));
    } catch {
      this.connecting = false;
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.connecting = false;
      this.attempts = 0;
      this.startHeartbeat();
      this.subscribed.forEach((uuid) => this.send({ action: "subscribe", job_uuid: uuid }));
    };
    this.ws.onmessage = (event) => {
      try {
        this.handle(JSON.parse(event.data));
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onerror = () => {
      this.connecting = false;
    };
    this.ws.onclose = () => {
      this.connecting = false;
      this.stopHeartbeat();
      this.scheduleReconnect();
    };
  }

  send(payload) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(payload));
  }

  subscribe(uuid) {
    this.subscribed.add(uuid);
    this.send({ action: "subscribe", job_uuid: uuid });
  }

  unsubscribe(uuid) {
    this.subscribed.delete(uuid);
    this.send({ action: "unsubscribe", job_uuid: uuid });
  }

  handle(msg) {
    if (msg.type !== "job_update" || !msg.update_type || !msg.data) return;
    const { job_uuid: jobUuid, update_type: kind, data } = msg;
    const label = data.name || (jobUuid || "").slice(0, 8);

    if (kind === "status") {
      const map = {
        completed: ["success", "Job completed", `${label} finished successfully.`],
        failed: ["error", "Job failed", `${label} stopped with an error.`],
        running: ["info", "Job started", `${label} is now running.`],
        paused: ["warning", "Job paused", `${label} has been paused.`],
        cancelled: ["warning", "Job cancelled", `${label} has been cancelled.`],
      };
      const [type, title, message] = map[data.status] || ["info", "Job update", `Status: ${data.status}`];
      addNotification({ type, title, message, jobUuid });
      dispatch("job-status-change", { jobUuid, status: data.status, data });
    } else if (kind === "progress") {
      dispatch("job-progress", { jobUuid, progress: data.progress || 0, data });
    } else if (kind === "log") {
      if (data.level === "error" || data.level === "warning") {
        addNotification({
          type: data.level === "error" ? "error" : "warning",
          title: `Job ${data.level}`,
          message: data.message || "Check the logs for details",
          jobUuid,
        });
      }
      dispatch("job-log", { jobUuid, data });
    } else if (kind === "error") {
      addNotification({ type: "error", title: "Job error", message: data.message || "An error occurred", jobUuid });
      dispatch("job-error", { jobUuid, data });
    }
  }

  startHeartbeat() {
    this.heartbeat = setInterval(() => this.send({ action: "ping" }), HEARTBEAT_MS);
  }

  stopHeartbeat() {
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = null;
  }

  scheduleReconnect() {
    if (!getToken() || this.attempts >= MAX_RECONNECT) return;
    this.attempts += 1;
    setTimeout(() => this.connect(), 1000 * 2 ** (this.attempts - 1));
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.subscribed.clear();
    this.attempts = 0;
  }
}

function dispatch(name, detail) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

export const jobSocket = new JobSocket();
