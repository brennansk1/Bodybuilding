"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/Logo";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(username, password);
      router.push(user.onboarding_complete ? "/dashboard" : "/onboarding");
    } catch {
      setError("Invalid username or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8 relative z-10 page-enter">
        <div className="text-center">
          <Logo size="lg" />
          <p className="h-section mt-3 text-travertine">All Is Ours</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white border border-ash rounded-card px-7 py-8 space-y-5 shadow-[0_8px_24px_rgba(26,24,22,0.06)]"
        >
          <div className="text-center space-y-1">
            <h2 className="h-display-sm">Welcome Back</h2>
            <p className="body-serif-sm italic text-iron">Sign in to continue your physique work.</p>
          </div>

          {error && (
            <div className="flex items-start gap-2 bg-blush border border-terracotta text-centurion text-xs py-2.5 px-3 rounded-button">
              <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          <div>
            <label htmlFor="username" className="label-field">Username</label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="input-field"
              placeholder="Enter your username"
            />
          </div>

          <div>
            <div className="flex items-baseline justify-between">
              <label htmlFor="password" className="label-field">Password</label>
              <a
                href="/auth/forgot"
                className="text-[10px] tracking-[0.15em] uppercase text-travertine hover:text-centurion transition-colors"
              >
                Forgot?
              </a>
            </div>
            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input-field pr-14"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-travertine hover:text-charcoal text-[10px] tracking-[0.15em] uppercase font-medium transition-colors"
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="btn-accent w-full disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 py-3"
          >
            {loading && (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {loading ? "Signing in…" : "Log In"}
          </button>

          <p className="text-center text-sm text-iron">
            New here?{" "}
            <a
              href="/auth/register"
              className="text-centurion hover:text-oxblood font-medium underline underline-offset-4 decoration-terracotta decoration-2 transition-colors"
            >
              Create an account
            </a>
          </p>
        </form>
      </div>
    </main>
  );
}
