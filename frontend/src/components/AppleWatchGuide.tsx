"use client";

import { useState } from "react";

type Tab = "hrv" | "rhr" | "sleep" | "apps";

interface AppleWatchGuideProps {
  initialTab?: Tab;
  onClose: () => void;
}

export default function AppleWatchGuide({ initialTab = "hrv", onClose }: AppleWatchGuideProps) {
  const [tab, setTab] = useState<Tab>(initialTab);

  return (
    <div
      className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-start sm:items-center justify-center p-0 sm:p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="bg-jungle-card border border-jungle-border rounded-none sm:rounded-2xl w-full sm:max-w-lg min-h-screen sm:min-h-0 sm:max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-jungle-border">
          <div className="flex items-center gap-2">
            <span className="text-xl">⌚</span>
            <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wider">Apple Watch Guide</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-jungle-deeper border border-jungle-border text-jungle-muted hover:text-jungle-accent flex items-center justify-center"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-jungle-border bg-jungle-deeper/40">
          {(["hrv", "rhr", "sleep", "apps"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2.5 text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                tab === t
                  ? "text-jungle-accent border-b-2 border-jungle-accent bg-jungle-card"
                  : "text-jungle-muted hover:text-jungle-text"
              }`}
            >
              {t === "rhr" ? "Resting HR" : t === "apps" ? "Apps" : t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 text-sm text-jungle-muted space-y-4">
          {tab === "hrv" && (
            <>
              <div>
                <h3 className="text-sm font-bold text-jungle-text mb-1">Heart Rate Variability</h3>
                <p className="text-[12px] text-jungle-dim">The single best recovery metric. Track first thing each morning.</p>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3 space-y-2">
                <p className="text-[11px] font-semibold text-jungle-accent uppercase tracking-wider">Where to find it</p>
                <ol className="text-[12px] space-y-1 list-decimal list-inside text-jungle-muted">
                  <li>Open the <span className="text-jungle-text font-medium">Health</span> app on iPhone</li>
                  <li>Tap <span className="text-jungle-text font-medium">Browse</span></li>
                  <li>Tap <span className="text-jungle-text font-medium">Heart</span></li>
                  <li>Tap <span className="text-jungle-text font-medium">Heart Rate Variability</span></li>
                </ol>
              </div>
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                <p className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider mb-1">Protocol</p>
                <p className="text-[12px] leading-snug">
                  For a clean morning reading, do a <span className="font-semibold">1-minute Breathe session</span> on
                  the watch <span className="font-semibold">before getting out of bed</span>. That logs a dedicated
                  HRV sample you can read later.
                </p>
              </div>
              <div className="bg-jungle-deeper/60 rounded-lg p-3">
                <p className="text-[11px] font-semibold text-jungle-muted uppercase tracking-wider mb-1">Note on format</p>
                <p className="text-[12px] leading-snug">
                  Apple reports <span className="font-mono">SDNN</span> (standard deviation of NN intervals).
                  Research-grade apps often use <span className="font-mono">RMSSD</span>. They measure slightly
                  different things but <span className="font-semibold text-jungle-text">trends behave the same</span> —
                  just pick one and stick with it.
                </p>
              </div>
            </>
          )}

          {tab === "rhr" && (
            <>
              <div>
                <h3 className="text-sm font-bold text-jungle-text mb-1">Resting Heart Rate</h3>
                <p className="text-[12px] text-jungle-dim">Morning RHR rises under fatigue, illness, and deep fatigue.</p>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3 space-y-2">
                <p className="text-[11px] font-semibold text-jungle-accent uppercase tracking-wider">Option A — On the watch</p>
                <ol className="text-[12px] space-y-1 list-decimal list-inside text-jungle-muted">
                  <li>Open the <span className="text-jungle-text font-medium">Heart Rate</span> app</li>
                  <li>Scroll with the Digital Crown</li>
                  <li>Find <span className="text-jungle-text font-medium">Resting Rate</span></li>
                </ol>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3 space-y-2">
                <p className="text-[11px] font-semibold text-jungle-accent uppercase tracking-wider">Option B — iPhone Health</p>
                <ol className="text-[12px] space-y-1 list-decimal list-inside text-jungle-muted">
                  <li>Open <span className="text-jungle-text font-medium">Health</span></li>
                  <li><span className="text-jungle-text font-medium">Browse → Heart</span></li>
                  <li>Tap <span className="text-jungle-text font-medium">Resting Heart Rate</span></li>
                </ol>
              </div>
              <div className="bg-jungle-deeper/60 rounded-lg p-3">
                <p className="text-[11px] font-semibold text-jungle-muted uppercase tracking-wider mb-1">What's normal</p>
                <p className="text-[12px] leading-snug">
                  Trained athletes usually sit in the <span className="font-mono">50–65 bpm</span> range.
                  A <span className="font-semibold text-jungle-text">+5 bpm spike</span> over baseline is an early
                  fatigue signal — scale volume that day.
                </p>
              </div>
            </>
          )}

          {tab === "sleep" && (
            <>
              <div>
                <h3 className="text-sm font-bold text-jungle-text mb-1">Sleep Tracking</h3>
                <p className="text-[12px] text-jungle-dim">The single biggest recovery lever — protect 7-9h.</p>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3 space-y-2">
                <p className="text-[11px] font-semibold text-jungle-accent uppercase tracking-wider">On the watch</p>
                <ol className="text-[12px] space-y-1 list-decimal list-inside text-jungle-muted">
                  <li>Open the <span className="text-jungle-text font-medium">Sleep</span> app</li>
                  <li>Check the previous night's stats on wake</li>
                  <li>Log total duration + quality (1-10 subjective)</li>
                </ol>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3 space-y-2">
                <p className="text-[11px] font-semibold text-jungle-accent uppercase tracking-wider">iPhone Health</p>
                <ol className="text-[12px] space-y-1 list-decimal list-inside text-jungle-muted">
                  <li>Open <span className="text-jungle-text font-medium">Health</span></li>
                  <li><span className="text-jungle-text font-medium">Browse → Sleep</span></li>
                  <li>See stages (Core / Deep / REM), total time, time in bed</li>
                </ol>
              </div>
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                <p className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider mb-1">Tip</p>
                <p className="text-[12px] leading-snug">
                  Wear the watch to sleep — set up a bedtime schedule in the Sleep app so it auto-enables
                  Sleep Focus and reduces wrist vibration overnight.
                </p>
              </div>
            </>
          )}

          {tab === "apps" && (
            <>
              <div>
                <h3 className="text-sm font-bold text-jungle-text mb-1">Recommended apps</h3>
                <p className="text-[12px] text-jungle-dim">Third-party apps that surface Apple Health data in one tap.</p>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3">
                <div className="flex items-baseline justify-between mb-1">
                  <p className="text-sm font-semibold text-jungle-text">Athlytic</p>
                  <p className="text-[10px] text-jungle-dim font-mono">$3.99/mo</p>
                </div>
                <p className="text-[12px] leading-snug">
                  HRV, RHR, and sleep all on one screen. Daily readiness score. Most actionable for athletes.
                </p>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3">
                <div className="flex items-baseline justify-between mb-1">
                  <p className="text-sm font-semibold text-jungle-text">Training Today</p>
                  <p className="text-[10px] text-jungle-dim font-mono">Free</p>
                </div>
                <p className="text-[12px] leading-snug">
                  Simple 0-100 readiness number. Good starting point before committing to a paid tracker.
                </p>
              </div>
              <div className="bg-jungle-deeper rounded-lg p-3">
                <div className="flex items-baseline justify-between mb-1">
                  <p className="text-sm font-semibold text-jungle-text">HRV4Training</p>
                  <p className="text-[10px] text-jungle-dim font-mono">$9.99 one-time</p>
                </div>
                <p className="text-[12px] leading-snug">
                  Research-grade RMSSD. Works with camera or Apple Watch. Used by the Italian national team. Best for
                  serious data nerds.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
