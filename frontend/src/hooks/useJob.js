"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useToast } from "@/hooks/useToast";
import { getPrefs } from "@/lib/prefs";
import { filesApi, jobsApi } from "@/lib/api";
import { formatNumber, saveBlob } from "@/lib/format";
import { addNotification } from "@/lib/notifications";
import { jobSocket } from "@/lib/ws";

const JobContext = createContext(null);

const POLL_MS = 2000;
const ACTIVE = new Set(["queued", "running", "retrying"]);
const DONE = new Set(["completed", "failed", "cancelled"]);

const EMPTY_MAPPER = { open: false, headers: [], filename: "", jobUuid: "", sheet: null, headerRow: 1 };

function beep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const a = new Ctx();
    [880, 1047, 880].forEach((f, i) => {
      const o = a.createOscillator();
      const g = a.createGain();
      o.type = "square";
      o.frequency.value = f;
      o.connect(g);
      g.connect(a.destination);
      g.gain.value = 0.04;
      o.start(a.currentTime + i * 0.16);
      o.stop(a.currentTime + i * 0.16 + 0.12);
    });
  } catch {
    /* audio blocked */
  }
}

function browserNotify(title, body) {
  try {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") {
      new Notification(title, { body, icon: "/favicon.png", tag: "scraply-job" });
    } else if (Notification.permission === "default") {
      Notification.requestPermission();
    }
  } catch {
    /* ignore */
  }
}

// Owns the "current job": the one the Controls page shows and the app bar acts on.
export function JobProvider({ children }) {
  const toast = useToast();
  const [job, setJob] = useState(null); // JobResponse from the API
  const [status, setStatus] = useState("pending");
  const [file, setFile] = useState(null); // { name, size } of the uploaded input
  const [mapped, setMapped] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mapper, setMapper] = useState(EMPTY_MAPPER);
  const poll = useRef(null);
  const statusRef = useRef("pending");
  const jobRef = useRef(null);
  const exportRef = useRef(null); // latest exportResult, for auto-export on completion

  // Latest status/job for callbacks that run outside render (polls, sockets, timers).
  useEffect(() => {
    statusRef.current = status;
    jobRef.current = job;
  }, [status, job]);

  const stopPolling = useCallback(() => {
    if (poll.current) clearInterval(poll.current);
    poll.current = null;
  }, []);

  // Apply a fresh JobResponse; fires completion side effects on running -> completed.
  const applyJob = useCallback(
    (next) => {
      if (!next) return;
      const prev = statusRef.current;
      const s = (next.status || "pending").toLowerCase();
      // A cancel confirmed locally must not flip back to running from a stale poll.
      if (prev === "cancelled" && s === "running") return;

      setJob(next);
      setStatus(s);
      if (next.display_filename) {
        setFile((f) => (f && f.name === next.display_filename ? f : { name: next.display_filename, size: f?.size }));
      }

      if (DONE.has(s)) stopPolling();

      if (prev === "running" && s === "completed") {
        const prefs = getPrefs();
        const processed = next.processed_rows || 0;
        const ok = next.successful_rows || 0;
        const rate = processed ? Math.round((ok / processed) * 100) : 0;
        addNotification({
          type: "success",
          title: "Job completed",
          message: `${next.display_filename || "Job"} finished - ${rate}% success, ${formatNumber(ok)} numbers.`,
          jobUuid: next.job_uuid,
        });
        toast("Extraction complete");
        if (prefs.completionSound) beep();
        if (prefs.browserNotifications) {
          browserNotify("Scraply - job completed", `${next.display_filename || "Job"}: ${rate}% success`);
        }
        if (prefs.autoExport) {
          setTimeout(() => exportRef.current?.(), 300);
        }
      }
      if (prev === "running" && s === "failed") {
        setError(next.error_message || "Job failed. Please check the logs.");
      }
    },
    [stopPolling, toast]
  );

  const refresh = useCallback(async () => {
    const current = jobRef.current;
    if (!current) return;
    try {
      applyJob(await jobsApi.get(current.job_uuid));
    } catch {
      /* transient - next poll retries */
    }
  }, [applyJob]);

  const startPolling = useCallback(() => {
    stopPolling();
    poll.current = setInterval(refresh, POLL_MS);
  }, [refresh, stopPolling]);

  // Initial load: running > queued > paused > most recent finished job > nothing.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        for (const s of ["running", "queued", "paused"]) {
          const { jobs } = await jobsApi.list({ status: s, pageSize: 1 });
          if (cancelled) return;
          if (jobs?.length) {
            const j = jobs[0];
            statusRef.current = j.status;
            setJob(j);
            setStatus(j.status);
            setMapped(true);
            setFile({ name: j.display_filename });
            if (ACTIVE.has(j.status)) startPolling();
            jobSocket.subscribe(j.job_uuid);
            return;
          }
        }
        let recent = null;
        for (const s of ["completed", "cancelled", "failed"]) {
          const { jobs } = await jobsApi.list({ status: s, pageSize: 1 });
          if (cancelled) return;
          const j = jobs?.[0];
          if (j && (!recent || new Date(j.created_at) > new Date(recent.created_at))) recent = j;
        }
        if (recent) {
          statusRef.current = recent.status;
          setJob(recent);
          setStatus(recent.status);
          setMapped(true);
          setFile({ name: recent.display_filename });
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  // Live updates from the WebSocket for the current job.
  useEffect(() => {
    const onStatus = (e) => {
      if (e.detail.jobUuid === jobRef.current?.job_uuid) refresh();
    };
    const onProgress = (e) => {
      if (e.detail.jobUuid === jobRef.current?.job_uuid) refresh();
    };
    window.addEventListener("job-status-change", onStatus);
    window.addEventListener("job-progress", onProgress);
    return () => {
      window.removeEventListener("job-status-change", onStatus);
      window.removeEventListener("job-progress", onProgress);
    };
  }, [refresh]);

  // ---- upload + column mapping -------------------------------------------
  const selectFile = useCallback(
    async (picked) => {
      if (!picked) return;
      const ext = picked.name.split(".").pop()?.toLowerCase();
      if (!["csv", "xlsx", "xls"].includes(ext)) {
        setError("Unsupported file. Upload a .csv, .xlsx or .xls file.");
        return;
      }
      setError("");
      setUploading(true);
      try {
        const created = await jobsApi.create({ name: `Scraply - ${picked.name}` });
        const uploaded = await filesApi.upload(picked, created.job_uuid);
        const info = await filesApi.headers(uploaded.filename);
        setFile({ name: picked.name, size: picked.size });
        setMapper({
          open: true,
          headers: info.headers || [],
          filename: picked.name,
          jobUuid: created.job_uuid,
          sheet: info.sheet ?? null,
          headerRow: info.header_row || 1,
        });
      } catch (e) {
        setError(e.message || "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    []
  );

  const confirmMapping = useCallback(
    async (columns) => {
      const { jobUuid, sheet, headerRow } = mapper;
      setMapper(EMPTY_MAPPER);
      try {
        const updated = await jobsApi.update(jobUuid, {
          config: { ...columns, sheet, header_row: headerRow },
        });
        stopPolling();
        statusRef.current = "pending";
        setJob(updated);
        setStatus("pending");
        setMapped(true);
        setError("");
        toast("Columns mapped - ready to start");
      } catch (e) {
        setError(e.message || "Could not save the column mapping");
      }
    },
    [mapper, stopPolling, toast]
  );

  const cancelMapping = useCallback(() => {
    setMapper(EMPTY_MAPPER);
    setFile(null);
  }, []);

  // Back to the empty dropzone (the job record stays in Extraction Logs).
  const removeFile = useCallback(() => {
    stopPolling();
    if (jobRef.current) jobSocket.unsubscribe(jobRef.current.job_uuid);
    statusRef.current = "pending";
    setJob(null);
    setStatus("pending");
    setFile(null);
    setMapped(false);
    setError("");
  }, [stopPolling]);

  // ---- lifecycle ----------------------------------------------------------
  const run = useCallback(
    async (fn, okMsg) => {
      const current = jobRef.current;
      if (!current) return;
      setError("");
      try {
        const next = await fn(current.job_uuid);
        applyJob(next);
        if (ACTIVE.has((next.status || "").toLowerCase())) {
          startPolling();
          jobSocket.subscribe(next.job_uuid);
        }
        if (okMsg) toast(okMsg);
      } catch (e) {
        setError(e.message);
      }
    },
    [applyJob, startPolling, toast]
  );

  const start = useCallback(() => run(jobsApi.start), [run]);
  const pause = useCallback(() => run(jobsApi.pause, "Job paused"), [run]);
  const resume = useCallback(() => run(jobsApi.resume, "Job resumed"), [run]);
  const retry = useCallback(() => run(jobsApi.retry, "Job requeued"), [run]);

  const cancel = useCallback(async () => {
    const current = jobRef.current;
    if (!current) return;
    stopPolling();
    setError("");
    try {
      const next = await jobsApi.cancel(current.job_uuid);
      statusRef.current = "cancelled";
      setJob(next);
      setStatus("cancelled");
      toast("Job cancelled");
    } catch (e) {
      setError(e.message);
    }
  }, [stopPolling, toast]);

  const exportResult = useCallback(async () => {
    const current = jobRef.current;
    if (!current) return;
    if (!(current.processed_rows > 0)) {
      setError("No data to export yet. Wait for processing to start.");
      return;
    }
    try {
      const blob = await jobsApi.download(current.job_uuid);
      const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
      const label = statusRef.current === "completed" ? "complete" : "partial";
      // Results always come back as Excel, whatever was uploaded.
      const name = `scraply_${label}_${current.processed_rows}rows_${stamp}.xlsx`;
      saveBlob(blob, name);
      toast(`Downloading ${name}`);
      setError("");
    } catch (e) {
      setError(e.message || "Failed to export. Output file may not exist yet.");
    }
  }, [toast]);
  useEffect(() => {
    exportRef.current = exportResult;
  }, [exportResult]);

  // ---- derived ------------------------------------------------------------
  const stats = useMemo(() => {
    const total = job?.total_rows || 0;
    const processed = job?.processed_rows || 0;
    const ok = job?.successful_rows || 0;
    const failed = job?.failed_rows || 0;
    return {
      total,
      processed,
      ok,
      failed,
      numbers: ok,
      emails: ok,
      missing: failed,
      pct: total ? Math.round((processed / total) * 100) : 0,
      rate: processed ? Math.round((ok / processed) * 100) : 0,
    };
  }, [job]);

  const running = status === "running";
  const queued = status === "queued" || status === "retrying";
  const paused = status === "paused";
  const finished = DONE.has(status);
  const hasData = stats.processed > 0;

  const value = {
    job,
    status,
    file,
    mapped,
    uploading,
    loading,
    error,
    setError,
    mapper,
    stats,
    flags: {
      running,
      queued,
      paused,
      finished,
      canStart: status === "pending" && mapped && !!job?.input_file_path,
      canPause: running,
      canResume: paused,
      canCancel: running || queued || paused,
      canRetry: status === "failed" || status === "cancelled",
      canExport: hasData,
      showDropzone: !file,
    },
    selectFile,
    confirmMapping,
    cancelMapping,
    removeFile,
    start,
    pause,
    resume,
    cancel,
    retry,
    exportResult,
    refresh,
  };

  return <JobContext.Provider value={value}>{children}</JobContext.Provider>;
}

export function useJob() {
  const ctx = useContext(JobContext);
  if (!ctx) throw new Error("useJob must be used inside <JobProvider>");
  return ctx;
}
