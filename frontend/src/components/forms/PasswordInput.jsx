"use client";

import { useState } from "react";

import Icon from "@/components/ui/Icon";

// Labelled password field with a show/hide eye button (.grp / .pw-eye styling).
export default function PasswordInput({ id, label, value, onChange, placeholder, minLength, autoComplete, disabled }) {
  const [show, setShow] = useState(false);
  return (
    <div className="grp">
      <label className="lbl" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="inp"
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        minLength={minLength}
        autoComplete={autoComplete}
        disabled={disabled}
        required
      />
      <button
        type="button"
        className="pw-eye"
        aria-label={show ? "Hide password" : "Show password"}
        onClick={() => setShow((v) => !v)}
      >
        <Icon name={show ? "eyeoff" : "eye"} />
      </button>
    </div>
  );
}
