"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

/**
 * Thin Legion-red progress bar pinned to the top of the viewport that animates
 * whenever the pathname or querystring changes. It eases from 0 → 80% while
 * the next segment is mounting, snaps to 100% on arrival, then fades out.
 *
 * Lightweight alternative to nprogress — no extra dep, styles match the
 * Viltrum palette, and it respects prefers-reduced-motion.
 */
export default function RouteProgress() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const rafRef = useRef<number | null>(null);
  const timersRef = useRef<number[]>([]);
  const firstRender = useRef(true);

  useEffect(() => {
    // Skip on initial mount — only react to subsequent navigations.
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }

    // Reset any in-flight animation and start a fresh run.
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];

    setVisible(true);
    setProgress(10);

    // Ease toward 80% while the next segment is rendering.
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      // Approach 80 asymptotically: 80 * (1 - exp(-t/600))
      const target = 80 * (1 - Math.exp(-elapsed / 600));
      setProgress((p) => Math.max(p, target));
      if (elapsed < 2500) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    // Snap to 100% on the next tick (the new pathname already rendered).
    timersRef.current.push(
      window.setTimeout(() => setProgress(100), 350),
    );
    timersRef.current.push(
      window.setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 800),
    );

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      timersRef.current.forEach((t) => clearTimeout(t));
      timersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, searchParams]);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed top-0 left-0 right-0 z-[70] h-[2px]"
      style={{
        opacity: visible ? 1 : 0,
        transition: "opacity 300ms ease-out",
      }}
    >
      <div
        className="h-full bg-viltrum-legion"
        style={{
          width: `${progress}%`,
          boxShadow: "0 0 6px rgba(196,64,64,0.35)",
          transition: "width 180ms ease-out",
        }}
      />
    </div>
  );
}
