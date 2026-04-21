"use client";

import { useEffect, useMemo, useState } from "react";

/**
 * Staggered per-character reveal for headline text, *in the intended font*.
 *
 * Earlier revisions used the tegaki-js library with a Caveat cursive
 * overlay, which produced a visible double-render (Contrail One + Caveat at
 * the same time). This replacement does the "drawn" effect via CSS on the
 * Contrail One glyphs themselves: each character fades/slides in with a
 * staggered delay so the title feels like it's being written, in the font
 * the brand actually uses.
 *
 * Reasons to skip the animation (all render static immediately):
 *   - `prefers-reduced-motion: reduce` user setting
 *   - `skipOnRevisit` + sessionStorage flag (one-shot per page per session)
 */
interface TegakiTitleProps {
  text: string;
  as?: "h1" | "h2" | "h3";
  size?: "display-xl" | "display-lg" | "display-md" | "display-sm";
  skipOnRevisit?: boolean;
  revisitKey?: string;
  className?: string;
}

const SIZE_CLASS: Record<NonNullable<TegakiTitleProps["size"]>, string> = {
  "display-xl": "h-display-xl",
  "display-lg": "h-display-lg",
  "display-md": "h-display-md",
  "display-sm": "h-display-sm",
};

// Per-character delay — low enough to feel snappy on long titles.
const STEP_MS = 55;
const BASE_DURATION_MS = 380;

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export default function TegakiTitle({
  text,
  as = "h1",
  size = "display-lg",
  skipOnRevisit = true,
  revisitKey,
  className = "",
}: TegakiTitleProps) {
  const Tag = as;
  const storageKey = useMemo(
    () => `viltrum.tegaki.seen.${revisitKey ?? text}`,
    [revisitKey, text],
  );

  // SSR + initial render: render static. Decide on animation client-side so
  // hydration matches and we can branch off prefers-reduced-motion etc.
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (prefersReducedMotion()) return;
    if (skipOnRevisit && typeof window !== "undefined") {
      try {
        if (window.sessionStorage.getItem(storageKey)) return;
        window.sessionStorage.setItem(storageKey, "1");
      } catch {
        /* sessionStorage unavailable — fall through and still animate */
      }
    }
    // Allow a tick so the DOM is painted with opacity:0 before we flip.
    const raf = window.requestAnimationFrame(() => setAnimate(true));
    return () => window.cancelAnimationFrame(raf);
  }, [skipOnRevisit, storageKey]);

  const chars = useMemo(() => Array.from(text), [text]);
  const sizeClass = SIZE_CLASS[size];

  return (
    <Tag
      className={`${sizeClass} ${className}`.trim()}
      aria-label={text}
    >
      {chars.map((ch, i) => {
        const delay = i * STEP_MS;
        const style: React.CSSProperties = animate
          ? {
              opacity: 1,
              transform: "translateY(0)",
              transition: `opacity ${BASE_DURATION_MS}ms ease-out ${delay}ms, transform ${BASE_DURATION_MS}ms ease-out ${delay}ms`,
            }
          : {
              opacity: 0,
              transform: "translateY(6px)",
              transition: "none",
            };
        return (
          <span
            key={`${i}-${ch}`}
            aria-hidden="true"
            style={{ display: "inline-block", whiteSpace: "pre", ...style }}
          >
            {ch}
          </span>
        );
      })}
    </Tag>
  );
}
