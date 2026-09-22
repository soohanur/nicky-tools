"use client";

import Icon from "@/components/ui/Icon";
import { useJob } from "@/hooks/useJob";
import { formatNumber } from "@/lib/format";

const LABEL = {
  pending: "Waiting to start",
  queued: "Queued - waiting for a worker",
  retrying: "Retrying",
  running: "Scraping company.info...",
  paused: "Paused",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const ROWS_PER_MIN = 220;

export default function ProgressCard() {
  const { status, stats, flags } = useJob();

  let eta = "Idle";
  if (flags.running) {
    const left = Math.max(0, stats.total - stats.processed);
    eta = stats.total ? `~${Math.max(1, Math.round(left / ROWS_PER_MIN))} min left` : "Starting...";
  } else if (flags.paused) eta = "Paused";
  else if (flags.queued) eta = "Queued";
  else if (status === "completed") eta = "Done";
  else if (status === "cancelled") eta = "Cancelled";
  else if (status === "failed") eta = "Failed";

  return (
    <div className="card">
      <div className="card-head">
        <h2>Progress</h2>
        <span className="dim small">{eta}</span>
      </div>
      <div className="progress-wrap">
        <div className="pr-top">
          <span>{LABEL[status] || "Waiting to start"}</span>
          <span>{stats.pct}%</span>
        </div>
        <div className={`prog${status === "completed" ? " green" : ""}`}>
          <i style={{ width: `${stats.pct}%` }} />
        </div>
      </div>
      <div className="row gap16 mt16 wrap dim small">
        <span className="row gap8">
          <span className="ri">
            <Icon name="rows" />
          </span>
          <b style={{ color: "var(--ink)" }}>{formatNumber(stats.processed)}</b>/{formatNumber(stats.total)} rows
        </span>
        <span className="row gap8">
          <span className="ri" style={{ color: "var(--ok)" }}>
            <Icon name="checkc" />
          </span>
          {formatNumber(stats.ok)} with contact
        </span>
        <span className="row gap8">
          <span className="ri" style={{ color: "var(--err)" }}>
            <Icon name="x" />
          </span>
          {formatNumber(stats.failed)} empty
        </span>
      </div>
    </div>
  );
}
