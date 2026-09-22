"use client";

import { useRef, useState } from "react";

import Icon from "@/components/ui/Icon";
import { useJob } from "@/hooks/useJob";
import { capitalize, formatBytes, formatNumber } from "@/lib/format";

// Dropzone -> file pill -> lifecycle buttons (Start / Pause / Resume / Retry / Cancel / Export).
export default function InputFileCard() {
  const { status, file, mapped, uploading, stats, flags, selectFile, removeFile, start, pause, resume, retry, cancel, exportResult } =
    useJob();
  const input = useRef(null);
  const [drag, setDrag] = useState(false);

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    if (uploading) return;
    const f = e.dataTransfer?.files?.[0];
    if (f) selectFile(f);
  };

  const onPick = (e) => {
    const f = e.target.files?.[0];
    if (f) selectFile(f);
    e.target.value = "";
  };

  const meta = [
    stats.total ? `${formatNumber(stats.total)} rows` : null,
    file?.size ? formatBytes(file.size) : null,
    mapped ? "mapped 4 columns" : "mapping pending",
  ]
    .filter(Boolean)
    .join(" · ");

  const tag = file ? status : "pending";
  const tagLabel = file ? capitalize(status) : "No job";

  return (
    <div className="card" id="uploadCard">
      <div className="card-head">
        <h2>Input File</h2>
        <span className={`tag ${tag}`}>{tagLabel}</span>
      </div>

      {flags.showDropzone ? (
        <div
          className={`dropzone${drag ? " drag" : ""}`}
          style={{ padding: 24, opacity: uploading ? 0.6 : 1 }}
          role="button"
          tabIndex={0}
          onClick={() => !uploading && input.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <div className="dz-ic" style={{ width: 48, height: 48, borderRadius: 14, marginBottom: 10 }}>
            <Icon name="upload" />
          </div>
          <h3>{uploading ? "Uploading..." : "Drop your CSV here"}</h3>
          <p>or click to browse - we&apos;ll map the columns next</p>
          <div className="formats">
            <span>.CSV</span>
            <span>.XLSX</span>
            <span>.XLS</span>
          </div>
          <input ref={input} type="file" accept=".csv,.xlsx,.xls" hidden onChange={onPick} />
        </div>
      ) : (
        <div className="file-pill" style={{ marginTop: 4 }}>
          <span className="fi">
            <Icon name="csv" />
          </span>
          <div className="grow">
            <b>{file.name}</b>
            <span>{meta}</span>
          </div>
          <button
            type="button"
            className="x"
            aria-label="Remove file"
            title="Remove file"
            disabled={flags.running || flags.queued}
            onClick={removeFile}
          >
            <Icon name="x" />
          </button>
        </div>
      )}

      <div className="lifecycle mt16">
        {!(flags.running || flags.paused || flags.queued || status === "completed") && (
          <button type="button" className="btn btn-primary" disabled={!flags.canStart} onClick={start}>
            <Icon name="play" />
            Start
          </button>
        )}
        {flags.queued && (
          <button type="button" className="btn btn-primary" disabled>
            <Icon name="clock" />
            Queued
          </button>
        )}
        {flags.running && (
          <button type="button" className="btn btn-warn" onClick={pause}>
            <Icon name="pause" />
            Pause
          </button>
        )}
        {flags.paused && (
          <button type="button" className="btn btn-primary" onClick={resume}>
            <Icon name="play" />
            Resume
          </button>
        )}
        {flags.canRetry && (
          <button type="button" className="btn btn-soft" onClick={retry}>
            <Icon name="retry" />
            Retry
          </button>
        )}
        {flags.canCancel && (
          <button type="button" className="btn btn-danger" onClick={cancel}>
            <Icon name="stop" />
            Cancel
          </button>
        )}
        <button type="button" className="btn btn-ghost" disabled={!flags.canExport} onClick={exportResult}>
          <Icon name="download" />
          Export CSV
        </button>
      </div>
    </div>
  );
}
