"use client";

import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import { useToast } from "@/hooks/useToast";
import { systemApi } from "@/lib/api";

const MIN = 1;
const MAX = 12;

// Parallel browser worker count (persisted to backend .env, restarts the worker).
export default function WorkerConfigCard() {
  const toast = useToast();
  const [value, setValue] = useState(4);
  const [saved, setSaved] = useState(4);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    systemApi
      .workerConfig()
      .then((c) => {
        setValue(c.max_workers);
        setSaved(c.max_workers);
      })
      .catch((e) => setError(e.message));
  }, []);

  const save = async () => {
    if (value === saved) {
      toast("No changes to save");
      return;
    }
    setSaving(true);
    setError("");
    setInfo("");
    try {
      const res = await systemApi.setWorkers(value);
      setSaved(res.max_workers);
      setInfo(res.message);
      toast(`Worker config saved: ${res.max_workers} workers`);
    } catch (e) {
      setError(e.message);
      setValue(saved);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <div className="card-head">
        <h2>Worker Configuration</h2>
      </div>
      <p className="dim small" style={{ marginTop: -8 }}>
        Number of parallel browser workers used to scrape. Higher = faster, but heavier on resources.
      </p>
      {error && <Alert onClose={() => setError("")}>{error}</Alert>}
      {info && (
        <Alert type="ok" onClose={() => setInfo("")}>
          {info}
        </Alert>
      )}
      <div className="row between mt16">
        <b>Max workers</b>
        <b style={{ color: "var(--blue-700)" }}>{value}</b>
      </div>
      <input
        type="range"
        min={MIN}
        max={MAX}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        style={{ width: "100%", accentColor: "var(--blue)", marginTop: 10 }}
        aria-label="Max workers"
      />
      <div className="row between tiny dim">
        <span>{MIN}</span>
        <span>{MAX}</span>
      </div>
      <button type="button" className="btn btn-primary mt24" disabled={saving} onClick={save}>
        {saving ? "Saving..." : "Save configuration"}
      </button>
    </div>
  );
}
