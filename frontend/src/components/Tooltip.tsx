"use client";

import { ReactNode, useState } from "react";
import { Info } from "./icons";

interface TooltipProps {
  /** Tooltip content — text or arbitrary JSX. */
  content: ReactNode;
  /** The visible trigger. Defaults to an Info icon. */
  children?: ReactNode;
  /** Position of the popover. Defaults to `top`. */
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}

const SIDE_CLASSES: Record<NonNullable<TooltipProps["side"]>, string> = {
  top:    "bottom-full left-1/2 -translate-x-1/2 mb-2",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  left:   "right-full top-1/2 -translate-y-1/2 mr-2",
  right:  "left-full top-1/2 -translate-y-1/2 ml-2",
};

export default function Tooltip({
  content,
  children,
  side = "top",
  className = "",
}: TooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <span
      className={`relative inline-flex items-center ${className}`.trim()}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label="More information"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center text-viltrum-pewter hover:text-viltrum-travertine focus-visible:text-viltrum-obsidian focus:outline-none"
      >
        {children ?? <Info className="w-3.5 h-3.5" />}
      </button>
      {open && (
        <span
          role="tooltip"
          className={`absolute z-50 ${SIDE_CLASSES[side]} w-48 max-w-xs rounded-card border border-viltrum-ash bg-white shadow-card p-2 text-[11px] text-viltrum-iron leading-snug pointer-events-none`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
