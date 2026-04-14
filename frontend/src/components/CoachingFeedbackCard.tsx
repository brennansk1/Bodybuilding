"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export interface CoachingMessage {
  severity: "info" | "warning" | "action";
  category: string;
  title: string;
  body: string;
  metric_value?: number | null;
  threshold?: number | null;
  meta?: Record<string, unknown>;
}

interface CoachingFeedbackCardProps {
  feedbackId: string | null;
  messages: CoachingMessage[];
  onDismiss?: () => void;
}

const SEVERITY_STYLES: Record<
  CoachingMessage["severity"],
  { border: string; bg: string; text: string; dot: string; label: string }
> = {
  info:    { border: "border-blue-500/40",   bg: "bg-blue-500/5",   text: "text-blue-400",   dot: "bg-blue-400",   label: "Observation" },
  warning: { border: "border-amber-500/40",  bg: "bg-amber-500/5",  text: "text-amber-400",  dot: "bg-amber-400",  label: "Heads up" },
  action:  { border: "border-red-500/40",    bg: "bg-red-500/5",    text: "text-red-400",    dot: "bg-red-400",    label: "Act this week" },
};

export default function CoachingFeedbackCard({
  feedbackId,
  messages,
  onDismiss,
}: CoachingFeedbackCardProps) {
  const [expanded, setExpanded] = useState<number | null>(0);
  const [dismissing, setDismissing] = useState(false);
  const [hidden, setHidden] = useState(false);

  if (!messages || messages.length === 0 || hidden) return null;

  const dismiss = async () => {
    if (!feedbackId) {
      setHidden(true);
      onDismiss?.();
      return;
    }
    setDismissing(true);
    try {
      await api.patch(`/checkin/coaching-feedback/${feedbackId}/dismiss`, {});
      setHidden(true);
      onDismiss?.();
    } catch {
      /* ignore */
    } finally {
      setDismissing(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <h3 className="text-xs font-bold text-jungle-muted uppercase tracking-wider">
          Coach&apos;s notes ({messages.length})
        </h3>
        {feedbackId && (
          <button
            onClick={dismiss}
            disabled={dismissing}
            className="text-[10px] text-jungle-dim hover:text-jungle-accent disabled:opacity-50"
          >
            {dismissing ? "Dismissing…" : "Dismiss all"}
          </button>
        )}
      </div>
      {messages.map((m, i) => {
        const s = SEVERITY_STYLES[m.severity] ?? SEVERITY_STYLES.info;
        const isOpen = expanded === i;
        return (
          <div
            key={i}
            className={`rounded-xl border-l-4 border-l-current ${s.border} ${s.bg} border border-r-transparent border-t-transparent border-b-transparent`}
            style={{ borderLeftColor: "currentColor" }}
          >
            <button
              type="button"
              onClick={() => setExpanded(isOpen ? null : i)}
              className="w-full text-left px-3 py-2.5 flex items-center gap-3"
            >
              <span className={`w-2 h-2 rounded-full ${s.dot} shrink-0`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-jungle-text truncate">{m.title}</p>
                <p className={`text-[10px] uppercase tracking-wider ${s.text}`}>{s.label}</p>
              </div>
              <svg
                className={`w-4 h-4 text-jungle-dim transition-transform shrink-0 ${isOpen ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {isOpen && (
              <div className="px-3 pb-3 pl-8 text-[12px] text-jungle-muted leading-relaxed">
                {m.body}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
