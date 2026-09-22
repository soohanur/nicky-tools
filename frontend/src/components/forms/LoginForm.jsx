"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AuthBrand from "@/components/forms/AuthBrand";
import PasswordInput from "@/components/forms/PasswordInput";
import Alert from "@/components/ui/Alert";
import { useAuth } from "@/hooks/useAuth";

export default function LoginForm() {
  const router = useRouter();
  const { login } = useAuth();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!identity || !password) {
      setError("Please fill in all fields");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await login(identity.trim(), password);
      router.replace("/");
    } catch (err) {
      setError(err.status === 401 ? "Invalid credentials. Please try again." : err.message);
      setLoading(false);
    }
  };

  return (
    <form className="auth-card" onSubmit={submit} noValidate>
      <AuthBrand />
      <h1>Welcome back</h1>
      <p className="lead">Sign in to your Scraply workspace.</p>

      {error && <Alert onClose={() => setError("")}>{error}</Alert>}

      <div className="grp">
        <label className="lbl" htmlFor="identity">
          Email or username
        </label>
        <input
          id="identity"
          className="inp"
          type="text"
          value={identity}
          onChange={(e) => setIdentity(e.target.value)}
          placeholder="you@company.com"
          autoComplete="username"
          disabled={loading}
          required
        />
      </div>
      <PasswordInput
        id="password"
        label="Password"
        value={password}
        onChange={setPassword}
        placeholder="••••••••"
        autoComplete="current-password"
        disabled={loading}
      />

      <div className="row-between">
        <label className="checkrow">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Remember me
        </label>
        <a href="#" onClick={(e) => e.preventDefault()} title="Contact your administrator to reset your password">
          Forgot password?
        </a>
      </div>

      <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
        {loading ? "Signing in..." : "Sign in"}
      </button>
      <div className="alt">
        No account? <Link href="/register/">Create one</Link>
      </div>
    </form>
  );
}
