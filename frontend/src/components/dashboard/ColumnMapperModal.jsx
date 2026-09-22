"use client";

import { useMemo, useState } from "react";

import Icon from "@/components/ui/Icon";
import { MAPPING_STEPS } from "@/data/site";

const EMPTY = Object.fromEntries(MAPPING_STEPS.map((s) => [s.key, ""]));

// Four-step wizard: pick which column holds business name, street, house
// number and city. Nothing is pre-selected: exports differ too much between
// deliveries and a wrong pre-fill is easy to miss.
export default function ColumnMapperModal({ open, filename, headers, sheet, headerRow, onConfirm, onCancel }) {
  const [step, setStepState] = useState(0);
  const [picks, setPicks] = useState(EMPTY);
  const [query, setQuery] = useState("");
  const [prevOpen, setPrevOpen] = useState(open);

  // Reset the wizard each time the modal opens (state derived from the `open` prop).
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setStepState(0);
      setPicks(EMPTY);
      setQuery("");
    }
  }

  const setStep = (next) => {
    setStepState(next);
    setQuery("");
  };

  const current = MAPPING_STEPS[step];
  const last = step === MAPPING_STEPS.length - 1;
  const canNext = !!picks[current.key];

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? headers.filter((h) => h.toLowerCase().includes(q)) : headers;
  }, [headers, query]);

  const meta = [
    `${headers.length} columns detected`,
    sheet ? `sheet ${sheet}` : null,
    headerRow > 1 ? `header on row ${headerRow}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const next = () => {
    if (!canNext) return;
    if (last) onConfirm(picks);
    else setStep(step + 1);
  };

  return (
    <div className={`modal${open ? " show" : ""}`} role="dialog" aria-modal="true" aria-hidden={!open}>
      <div className="box">
        <div className="m-head">
          <h2>Map your CSV columns</h2>
          <p>
            {filename} · {meta}
          </p>
        </div>
        <div className="stepper">
          {MAPPING_STEPS.map((s, i) => (
            <div key={s.key} className={`st${i < step ? " done" : i === step ? " cur" : ""}`} />
          ))}
        </div>
        <div className="m-body">
          <div className="qn">
            Step {step + 1} of {MAPPING_STEPS.length}
          </div>
          <h3>{current.question}</h3>
          {headers.length > 10 && (
            <label className="field" style={{ marginBottom: 10 }}>
              <Icon name="search" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter columns..."
                aria-label="Filter columns"
              />
            </label>
          )}
          <div className="col-opts">
            {visible.length === 0 ? (
              <div className="empty" style={{ padding: 24 }}>
                <h3>No matching column</h3>
              </div>
            ) : (
              visible.map((h) => {
                const sel = picks[current.key] === h;
                return (
                  <button
                    key={h}
                    type="button"
                    className={`col-opt${sel ? " sel" : ""}`}
                    onClick={() => setPicks((p) => ({ ...p, [current.key]: h }))}
                  >
                    <span className="rb" />
                    {h}
                  </button>
                );
              })
            )}
          </div>
        </div>
        <div className="m-foot">
          <button
            type="button"
            className="btn btn-ghost"
            style={{ visibility: step ? "visible" : "hidden" }}
            onClick={() => setStep(Math.max(0, step - 1))}
          >
            <Icon name="back" />
            Back
          </button>
          <div className="row gap8">
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              Cancel
            </button>
            <button type="button" className="btn btn-primary" disabled={!canNext} onClick={next}>
              {last ? "Confirm mapping" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
