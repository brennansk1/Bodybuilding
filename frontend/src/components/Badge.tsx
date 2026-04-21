"use client";

import { ReactNode } from "react";

type BadgeTone =
  | "passed"     // success / tier threshold met
  | "pending"    // needs attention, 'X pts away'
  | "warning"    // aureus — watch this metric
  | "info"       // adriatic — developing
  | "accent"     // legion — primary alert
  | "neutral"    // ash — generic chip
  | "dark";      // obsidian — premier 'Stage ready' pill

interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  icon?: ReactNode;
  className?: string;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  passed:  "bg-viltrum-laurel-bg text-viltrum-laurel",
  pending: "bg-viltrum-blush text-viltrum-centurion",
  warning: "bg-viltrum-aureus-bg text-viltrum-aureus",
  info:    "bg-viltrum-adriatic-bg text-viltrum-adriatic",
  accent:  "bg-viltrum-blush text-viltrum-legion",
  neutral: "bg-viltrum-limestone text-viltrum-iron",
  dark:    "bg-viltrum-obsidian text-white",
};

export default function Badge({ tone = "neutral", children, icon, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1 rounded-pill ${TONE_CLASSES[tone]} ${className}`.trim()}
    >
      {icon}
      {children}
    </span>
  );
}
