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
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-canopy-gradient">
      <div className="text-center space-y-8 max-w-lg">
        <Logo size="xl" showTagline />

        <p className="text-jungle-muted text-base sm:text-lg leading-relaxed">
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
          <a href="/auth/login" className="btn-primary text-center">
            Log In
          </a>
          <a href="/auth/register" className="btn-secondary text-center">
            Create Account
          </a>
        </div>

        {/* Feature highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-12 text-left">
          <FeatureCard
            icon="1"
            title="Physique Analysis"
            desc="Track muscle development against your division's ideal proportions with precision scoring"
          />
          <FeatureCard
            icon="2"
            title="Smart Programming"
            desc="Auto-adjusting training volume based on your recovery — deloads when you need them"
          />
          <FeatureCard
            icon="3"
            title="Precision Nutrition"
            desc="Phase-aware meal plans with coach-level food selection and peak week protocols"
          />
        </div>
      </div>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  desc,
}: {
  icon: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="card card-hover">
      <div className="w-8 h-8 rounded-lg bg-jungle-primary/20 flex items-center justify-center mb-3">
        <span className="text-jungle-accent font-bold text-sm">{icon}</span>
      </div>
      <h3 className="text-sm font-semibold text-jungle-text mb-1">{title}</h3>
      <p className="text-xs text-jungle-muted leading-relaxed">{desc}</p>
    </div>
  );
}
