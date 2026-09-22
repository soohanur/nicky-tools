"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import AuthBrand from "@/components/forms/AuthBrand";
import PasswordInput from "@/components/forms/PasswordInput";
import Alert from "@/components/ui/Alert";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";

export default function RegisterForm() {
  const router = useRouter();
  const toast = useToast();
  const { register, login } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email || !username || !password || !confirm || !adminKey) {
      setError("Please fill in all fields");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await register({ email: email.trim(), username: username.trim(), password, adminKey: adminKey.trim() });
      toast("Account created - signing you in...");
      // Sign in right away so the new user lands on the dashboard.
      await login(username.trim(), password);
      router.replace("/");
    } catch (err) {
      setError(err.message || "Registration failed. Check your admin key and try again.");
      setLoading(false);
    }
  };

  return (
    <form className="auth-card" onSubmit={submit} noValidate>
      <AuthBrand />
      <h1>Create account</h1>
      <p className="lead">Register with admin authorization.</p>

      {error && <Alert onClose={() => setError("")}>{error}</Alert>}

      <div className="grp">
        <label className="lbl" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="inp"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          autoComplete="email"
          disabled={loading}
          required
        />
      </div>
      <div className="grp">
        <label className="lbl" htmlFor="username">
          Username
        </label>
        <input
          id="username"
          className="inp"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="yourname"
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
        placeholder="At least 8 characters"
        minLength={8}
        autoComplete="new-password"
        disabled={loading}
      />
      <PasswordInput
        id="confirm"
        label="Confirm Password"
        value={confirm}
        onChange={setConfirm}
        placeholder="Repeat password"
        autoComplete="new-password"
        disabled={loading}
      />
      <div className="grp">
        <label className="lbl" htmlFor="adminKey">
          Admin Secret Key
        </label>
        <input
          id="adminKey"
          className="inp"
          type="password"
          value={adminKey}
          onChange={(e) => setAdminKey(e.target.value)}
          placeholder="Provided by your administrator"
          autoComplete="off"
          disabled={loading}
          required
        />
        <p className="tiny dim" style={{ margin: "6px 0 0" }}>
          Required for registration. Contact your administrator.
        </p>
      </div>

      <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
        {loading ? "Creating account..." : "Create Account"}
      </button>
      <div className="alt">
        Already have an account? <Link href="/login/">Sign in</Link>
      </div>
    </form>
  );
}
