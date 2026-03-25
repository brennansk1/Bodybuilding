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
      setError("Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center p-4 bg-canopy-gradient">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <Logo size="lg" />
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4">
          <h2 className="text-xl font-semibold text-center">Welcome Back</h2>
          {error && (
            <p className="text-jungle-danger text-sm text-center bg-jungle-danger/10 py-2 rounded-lg">
              {error}
            </p>
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
              placeholder="e.g. Brennansk"
            />
          </div>
          <div>
            <label htmlFor="password" className="label-field">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="input-field"
            />
          </div>
          <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-50">
            {loading ? "Logging in..." : "Log In"}
          </button>
          <p className="text-center text-sm text-jungle-muted">
            No account?{" "}
            <a href="/auth/register" className="text-jungle-accent hover:underline">
              Register
            </a>
          </p>
        </form>
      </div>
    </main>
  );
}
