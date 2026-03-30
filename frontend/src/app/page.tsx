"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Logo from "@/components/Logo";

export default function Home() {
  const [health, setHealth] = useState<{
    status: string;
    version: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ status: string; version: string }>("/health")
      .then(setHealth)
      .catch(() => setError("Backend unavailable"));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-canopy-gradient relative overflow-hidden">
      {/* Subtle radial glow behind logo */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-jungle-accent/5 rounded-full blur-3xl pointer-events-none" />

      <div className="text-center space-y-8 max-w-lg relative z-10 page-enter">
        <Logo size="xl" showTagline />

        <p className="text-jungle-muted text-base sm:text-lg leading-relaxed max-w-md mx-auto">
          Your personal Olympia-level coaching system. Personalized training
          programs, precision nutrition, and physique tracking — all calibrated
          to your division and competition timeline.
        </p>

        <div className="card">
          {error ? (
            <p className="text-jungle-danger text-sm">{error}</p>
          ) : health ? (
            <div className="flex items-center justify-center gap-2">
              <span className="w-2 h-2 rounded-full bg-jungle-success animate-pulse" />
              <p className="text-jungle-fern text-sm">
                System online — v{health.version}
              </p>
            </div>
          ) : (
            <div className="flex items-center justify-center gap-2">
              <span className="w-2 h-2 rounded-full bg-jungle-dim animate-pulse" />
              <p className="text-jungle-muted text-sm">Connecting...</p>
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a href="/auth/login" className="btn-primary text-center text-base px-8 py-3">
            Log In
          </a>
          <a href="/auth/register" className="btn-secondary text-center text-base px-8 py-3">
            Create Account
          </a>
        </div>

        {/* Feature highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-12 text-left">
          <FeatureCard
            num="01"
            title="Physique Analysis"
            desc="Track muscle development against your division's ideal proportions with precision scoring"
          />
          <FeatureCard
            num="02"
            title="Smart Programming"
            desc="Auto-adjusting training volume based on your recovery — deloads when you need them"
          />
          <FeatureCard
            num="03"
            title="Precision Nutrition"
            desc="Phase-aware meal plans with coach-level food selection and peak week protocols"
          />
        </div>
      </div>
    </main>
  );
}

function FeatureCard({
  num,
  title,
  desc,
}: {
  num: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="card card-hover group">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] text-jungle-accent/60 font-mono font-bold tracking-widest">{num}</span>
        <div className="h-px flex-1 bg-jungle-border/40" />
      </div>
      <h3 className="text-sm font-semibold text-jungle-text mb-1.5 group-hover:text-jungle-accent transition-colors">
        {title}
      </h3>
      <p className="text-xs text-jungle-muted leading-relaxed">{desc}</p>
    </div>
  );
}
