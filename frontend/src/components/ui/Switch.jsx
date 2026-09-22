"use client";

// Toggle switch (Settings page). Styled by .switch in globals.css.
export default function Switch({ checked, onChange, label }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} aria-label={label} />
    </label>
  );
}
