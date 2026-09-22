"use client";

import { useMemo, useState } from "react";

import Alert from "@/components/ui/Alert";
import Icon from "@/components/ui/Icon";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/hooks/useToast";
import { jobsApi } from "@/lib/api";
import { capitalize, formatDate, formatNumber, saveBlob, stripExt } from "@/lib/format";

const AVATAR = {
  completed: "ic-green",
  failed: "ic-red",
  cancelled: "ic-amber",
  running: "ic-blue",
  queued: "ic-blue",
  retrying: "ic-blue",
  paused: "ic-purple",
  pending: "ic-blue",
};

const REFRESH_MS = 5000;
const NONE = [];

async function loadJobs() {
  const { jobs } = await jobsApi.list({ pageSize: 100 });
  return jobs || [];
}

// Every job, newest first, with download of the enriched result.
export default function ExtractionLogsTable() {
  const toast = useToast();
  const { data, loading, error: loadError, setData } = useFetch(loadJobs, { every: REFRESH_MS });
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  const jobs = data || NONE;
  const message = error || loadError;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return jobs;
    return jobs.filter(
      (j) => (j.display_filename || "").toLowerCase().includes(q) || (j.name || "").toLowerCase().includes(q)
    );
  }, [jobs, query]);

  const download = async (j) => {
    if (!(j.processed_rows > 0)) return;
    try {
      const blob = await jobsApi.download(j.job_uuid);
      // Results always come back as Excel, whatever was uploaded.
      saveBlob(blob, `${stripExt(j.display_filename || "output")}_enriched.xlsx`);
      toast("Downloading file...");
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (j) => {
    if (!window.confirm(`Delete "${j.display_filename || j.name}"?`)) return;
    try {
      await jobsApi.remove(j.job_uuid);
      setData(jobs.filter((x) => x.job_uuid !== j.job_uuid));
      toast("Deleted");
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="card flush">
      <div className="card-head" style={{ padding: "20px 22px 0", margin: 0 }}>
        <h2>Extraction Logs</h2>
        <label className="field" style={{ width: 220 }}>
          <Icon name="search" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search jobs..." />
        </label>
      </div>
      {message && (
        <div style={{ padding: "16px 22px 0" }}>
          <Alert onClose={() => setError("")}>{message}</Alert>
        </div>
      )}
      <div className="table-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Job</th>
              <th>Status</th>
              <th>Rows</th>
              <th>Success</th>
              <th>Created</th>
              <th className="right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="center-cell">
                  <div className="spinner" />
                </td>
              </tr>
            ) : visible.length === 0 ? (
              <tr>
                <td colSpan={6} className="center-cell">
                  <div className="empty" style={{ padding: 24 }}>
                    <div className="ei">
                      <Icon name="doc" />
                    </div>
                    <h3>{query ? "No matching jobs" : "No jobs yet"}</h3>
                    <p>{query ? "Try a different search term." : "Finished jobs will appear here."}</p>
                  </div>
                </td>
              </tr>
            ) : (
              visible.map((j) => {
                const processed = j.processed_rows || 0;
                const ok = j.successful_rows || 0;
                const rate = processed ? `${Math.round((ok / processed) * 100)}%` : "-";
                const canDownload = processed > 0;
                return (
                  <tr key={j.job_uuid}>
                    <td>
                      <div className="nm">
                        <span className={`av ${AVATAR[j.status] || "ic-blue"}`}>
                          <Icon name="spider" />
                        </span>
                        <div>
                          <b>{j.display_filename || j.name}</b>
                          <span>job #{j.id}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`tag ${j.status}`}>{capitalize(j.status)}</span>
                    </td>
                    <td>
                      {formatNumber(processed)}
                      <span className="dim"> / {formatNumber(j.total_rows || 0)}</span>
                    </td>
                    <td className="b">{rate}</td>
                    <td className="dim">{formatDate(j.created_at)}</td>
                    <td>
                      <div className="rowact">
                        <button
                          type="button"
                          className="dl"
                          title={canDownload ? "Download enriched file" : "No results yet"}
                          aria-label="Download"
                          disabled={!canDownload}
                          style={canDownload ? undefined : { opacity: 0.4 }}
                          onClick={() => download(j)}
                        >
                          <Icon name="download" />
                        </button>
                        <button
                          type="button"
                          className="del"
                          title="Delete job"
                          aria-label="Delete"
                          disabled={j.status === "running" || j.status === "queued"}
                          style={j.status === "running" || j.status === "queued" ? { opacity: 0.4 } : undefined}
                          onClick={() => remove(j)}
                        >
                          <Icon name="trash" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
