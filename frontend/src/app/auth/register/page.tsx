"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/Logo";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const passwordStrength = password.length === 0 ? null
    : password.length < 8 ? "weak"
    : password.length < 12 && /[A-Z]/.test(password) && /[0-9]/.test(password) ? "medium"
    : password.length >= 12 || (/[A-Z]/.test(password) && /[0-9]/.test(password) && /[^a-zA-Z0-9]/.test(password)) ? "strong"
    : "medium";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (username.length < 3) {
      setError("Username must be at least 3 characters");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await register(email, username, password);
      router.push("/onboarding");
    } catch {
      setError("Registration failed — email or username may already be taken");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center p-4 bg-canopy-gradient">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <Logo size="lg" />
          <p className="text-jungle-dim text-sm mt-2">All Is Ours</p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4">
          <h2 className="text-xl font-semibold text-center">Create Account</h2>
          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 text-red-400 text-sm py-2.5 px-3 rounded-lg">
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {error}
            </div>
          )}
          <div>
            <label className="label-field">Email</label>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="input-field"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="label-field">Username</label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              className="input-field"
              placeholder="Choose a username"
            />
            {username.length > 0 && username.length < 3 && (
              <p className="text-[10px] text-red-400 mt-1">Must be at least 3 characters</p>
            )}
          </div>
          <div>
            <label className="label-field">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="input-field pr-10"
                placeholder="Min 8 characters"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-jungle-dim hover:text-jungle-muted text-xs"
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {passwordStrength && (
              <div className="flex items-center gap-2 mt-1.5">
                <div className="flex gap-0.5 flex-1">
                  <div className={`h-1 flex-1 rounded-full ${passwordStrength === "weak" ? "bg-red-400" : "bg-green-400"}`} />
                  <div className={`h-1 flex-1 rounded-full ${passwordStrength === "medium" || passwordStrength === "strong" ? "bg-green-400" : "bg-jungle-deeper"}`} />
                  <div className={`h-1 flex-1 rounded-full ${passwordStrength === "strong" ? "bg-green-400" : "bg-jungle-deeper"}`} />
                </div>
                <span className={`text-[10px] font-medium ${
                  passwordStrength === "weak" ? "text-red-400" : passwordStrength === "medium" ? "text-yellow-400" : "text-green-400"
                }`}>
                  {passwordStrength === "weak" ? "Too short" : passwordStrength === "medium" ? "Good" : "Strong"}
                </span>
              </div>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !email || !username || !password}
            className="btn-primary w-full disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading && (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {loading ? "Creating account..." : "Create Account"}
          </button>
          <p className="text-center text-sm text-jungle-muted">
            Already have an account?{" "}
            <a href="/auth/login" className="text-jungle-accent hover:underline font-medium">
              Log in
            </a>
          </p>
        </form>
      </div>
    </main>
  );
}
