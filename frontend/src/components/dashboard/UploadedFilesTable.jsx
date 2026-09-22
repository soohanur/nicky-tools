"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import Alert from "@/components/ui/Alert";
import Icon from "@/components/ui/Icon";
import { useFetch } from "@/hooks/useFetch";
import { useJob } from "@/hooks/useJob";
import { useToast } from "@/hooks/useToast";
import { filesApi, jobsApi } from "@/lib/api";
import { formatBytes, formatDate, formatNumber, saveBlob } from "@/lib/format";

// Input files plus the row count their job discovered.
async function loadFiles() {
  const [{ files }, { jobs }] = await Promise.all([
    filesApi.inputs(),
    jobsApi.list({ pageSize: 100 }).catch(() => ({ jobs: [] })),
  ]);
  const rows = {}; // stored filename -> total_rows
  (jobs || []).forEach((j) => {
    if (j.input_file_path && j.total_rows) rows[j.input_file_path.split("/").pop()] = j.total_rows;
  });
  return { files: files || [], rows };
}

// Input files of the current user's jobs (backend: /files/inputs).
export default function UploadedFilesTable() {
  const router = useRouter();
  const toast = useToast();
  const { flags } = useJob();
  const { data, loading, error: loadError, setData } = useFetch(loadFiles);
  const [error, setError] = useState("");

  const files = data?.files || [];
  const rows = data?.rows || {};
  const message = error || loadError;

  const download = async (f) => {
    try {
      saveBlob(await filesApi.download(f.filename), f.display_name || f.filename);
      toast("Downloading file...");
    } catch (e) {
      setError(e.message);
    }
  };

  const remove = async (f) => {
    if (!window.confirm(`Delete ${f.display_name || f.filename}?`)) return;
    try {
      await filesApi.remove(f.filename, "input");
      setData({ ...data, files: files.filter((x) => x.filename !== f.filename) });
      toast("Deleted");
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="card flush">
      <div className="card-head" style={{ padding: "20px 22px 0", margin: 0 }}>
        <h2>Uploaded Files</h2>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!flags.showDropzone}
          title={flags.showDropzone ? "Upload a new file" : "Remove the current file first"}
          onClick={() => router.push("/")}
        >
          <Icon name="upload" />
          Upload
        </button>
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
              <th>File</th>
              <th>Rows</th>
              <th>Size</th>
              <th>Uploaded</th>
              <th className="right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="center-cell">
                  <div className="spinner" />
                </td>
              </tr>
            ) : files.length === 0 ? (
              <tr>
                <td colSpan={5} className="center-cell">
                  <div className="empty" style={{ padding: 24 }}>
                    <div className="ei">
                      <Icon name="folder" />
                    </div>
                    <h3>No files yet</h3>
                    <p>Upload a CSV on the Controls page to get started.</p>
                  </div>
                </td>
              </tr>
            ) : (
              files.map((f) => (
                <tr key={f.filename}>
                  <td>
                    <div className="nm">
                      <span className="av ic-blue">
                        <Icon name="csv" />
                      </span>
                      <div>
                        <b>{f.display_name || f.filename}</b>
                        <span>input file</span>
                      </div>
                    </div>
                  </td>
                  <td>{rows[f.filename] ? formatNumber(rows[f.filename]) : <span className="dim">-</span>}</td>
                  <td className="dim">{formatBytes(f.size)}</td>
                  <td className="dim">{formatDate(f.created_at)}</td>
                  <td>
                    <div className="rowact">
                      <button type="button" className="dl" title="Download" aria-label="Download" onClick={() => download(f)}>
                        <Icon name="download" />
                      </button>
                      <button type="button" className="del" title="Delete" aria-label="Delete" onClick={() => remove(f)}>
                        <Icon name="trash" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
