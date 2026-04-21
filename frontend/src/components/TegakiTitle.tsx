"use client";

import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Stroke-by-stroke handwriting reveal for headline text.
 *
 * UX pattern: a cursive Caveat stroke animation plays for ~1.2s, then fades
 * out and reveals the Contrail One wordmark that was beneath it the whole
 * time. The Contrail text carries the permanent Viltrum brand; Caveat is
 * just the intro flourish.
 *
 * Reasons to skip the animation:
 *   - `prefers-reduced-motion: reduce` user setting
 *   - `skipOnRevisit` + sessionStorage flag (e.g. page-scoped one-shot)
 *   - Tegaki library fails to load (graceful degradation)
 *
 * Usage:
 *   <TegakiTitle text="Dashboard" as="h1" size="display-lg" />
 */

// Defer-load the Tegaki lib so SSR doesn't choke on a browser-only dep.
type TegakiRenderer = React.ComponentType<{
  font: unknown;
  children: string;
  style?: React.CSSProperties;
  className?: string;
  onAnimationEnd?: () => void;
}>;

interface TegakiTitleProps {
  text: string;
  /** Tag rendered for the static Contrail One title. Defaults to `h1`. */
  as?: "h1" | "h2" | "h3";
  /** Contrail-One size token. Maps to one of the `h-display-*` classes. */
  size?: "display-xl" | "display-lg" | "display-md" | "display-sm";
  /** Skip the animation after first render in a session. */
  skipOnRevisit?: boolean;
  /** Unique key for session-storage skipping. Defaults to the text value. */
  revisitKey?: string;
  className?: string;
}

const SIZE_CLASS: Record<NonNullable<TegakiTitleProps["size"]>, string> = {
  "display-xl": "h-display-xl",
  "display-lg": "h-display-lg",
  "display-md": "h-display-md",
  "display-sm": "h-display-sm",
};

// Match the Caveat overlay to the Contrail text metrics roughly — Caveat is
// condensed so we bump it a little for visual parity.
const CAVEAT_FONT_SIZE: Record<NonNullable<TegakiTitleProps["size"]>, string> = {
  "display-xl": "64px",
  "display-lg": "56px",
  "display-md": "44px",
  "display-sm": "34px",
};

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

  // Start assuming no animation so SSR matches initial client render.
  const [phase, setPhase] = useState<"idle" | "drawing" | "done">("idle");
  const [TegakiMod, setTegakiMod] = useState<{
    Renderer: TegakiRenderer;
    font: unknown;
  } | null>(null);
  const didStart = useRef(false);

  useEffect(() => {
    if (didStart.current) return;
    didStart.current = true;
    if (prefersReducedMotion()) {
      setPhase("done");
      return;
    }
    if (skipOnRevisit && typeof window !== "undefined") {
      try {
        if (window.sessionStorage.getItem(storageKey)) {
          setPhase("done");
          return;
        }
      } catch {
        /* sessionStorage unavailable — continue */
      }
    }

    let cancelled = false;
    // Dynamically import the Tegaki React entrypoint + the Caveat font bundle.
    Promise.all([
      import("tegaki/react").catch(() => null),
      import("tegaki/fonts/caveat").catch(() => null),
    ])
      .then(([reactMod, fontMod]) => {
        if (cancelled) return;
        if (!reactMod || !fontMod) {
          setPhase("done");
          return;
        }
        const Renderer = (reactMod as { TegakiRenderer: TegakiRenderer }).TegakiRenderer;
        const font = (fontMod as { default: unknown }).default ?? fontMod;
        setTegakiMod({ Renderer, font });
        setPhase("drawing");
      })
      .catch(() => setPhase("done"));

    return () => {
      cancelled = true;
    };
  }, [skipOnRevisit, storageKey]);

  // When the animation finishes, persist the skip flag.
  const handleAnimationEnd = () => {
    if (skipOnRevisit && typeof window !== "undefined") {
      try {
        window.sessionStorage.setItem(storageKey, "1");
      } catch {
        /* no-op */
      }
    }
    // Soft cross-fade: wait a tick, then drop the overlay.
    setTimeout(() => setPhase("done"), 280);
  };

  const sizeClass = SIZE_CLASS[size];

  return (
    <span className={`relative inline-block ${className}`.trim()}>
      <Tag className={sizeClass}>{text}</Tag>
      {phase === "drawing" && TegakiMod && (
        <span
          aria-hidden="true"
          className="absolute inset-0 flex items-center pointer-events-none transition-opacity duration-300"
          style={{ color: "#1A1816" }}
        >
          <TegakiMod.Renderer
            font={TegakiMod.font}
            style={{ fontSize: CAVEAT_FONT_SIZE[size], lineHeight: 1 }}
            onAnimationEnd={handleAnimationEnd}
          >
            {text}
          </TegakiMod.Renderer>
        </span>
      )}
    </span>
  );
}
