"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import ViltrumLoader from "./ViltrumLoader";

/**
 * Global client-side navigation loader.
 *
 * App Router only mounts `loading.tsx` when a segment is truly suspended on
 * the server. Most Viltrum pages are `"use client"` — they render instantly
 * with empty state and do their own data fetches — so `loading.tsx` never
 * shows between most navigations. This component fills that gap:
 *
 *  1. It captures every internal link click at the document level.
 *  2. It waits `SHOW_DELAY_MS` before revealing the overlay so fast navs
 *     (same-page hashes, instant cache hits) never produce a loader flash.
 *  3. When `usePathname` / `useSearchParams` updates, the new route has
 *     mounted — the overlay dismisses.
 *  4. A `MAX_VISIBLE_MS` hard ceiling keeps a stale state from trapping the
 *     user if something goes sideways (e.g. programmatic navigation that
 *     never resolves).
 *
 * Respects `prefers-reduced-motion` via `ViltrumLoader`'s own CSS.
 */
const SHOW_DELAY_MS = 220;
const MAX_VISIBLE_MS = 12_000;

export default function NavLoader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, setPending] = useState(false);
  const [visible, setVisible] = useState(false);

  const showTimerRef = useRef<number | null>(null);
  const ceilingTimerRef = useRef<number | null>(null);

  // ── Start: any same-origin internal anchor click begins a nav ─────────────
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        e.defaultPrevented ||
        e.button !== 0 ||
        e.metaKey ||
        e.ctrlKey ||
        e.shiftKey ||
        e.altKey
      ) {
        return;
      }
      const anchor = (e.target as HTMLElement | null)?.closest?.("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href) return;
      if (anchor.getAttribute("target") === "_blank") return;
      if (href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:") || href.startsWith("javascript:")) {
        return;
      }
      // Same-origin only.
      let target: URL;
      try {
        target = new URL(href, window.location.href);
      } catch {
        return;
      }
      if (target.origin !== window.location.origin) return;
      // Same path + same query = no nav.
      const currentUrl = new URL(window.location.href);
      if (target.pathname === currentUrl.pathname && target.search === currentUrl.search) {
        return;
      }
      beginNav();
    }

    function beginNav() {
      setPending(true);
      if (showTimerRef.current != null) window.clearTimeout(showTimerRef.current);
      if (ceilingTimerRef.current != null) window.clearTimeout(ceilingTimerRef.current);
      showTimerRef.current = window.setTimeout(() => setVisible(true), SHOW_DELAY_MS);
      ceilingTimerRef.current = window.setTimeout(finishNav, MAX_VISIBLE_MS);
    }

    function finishNav() {
      setPending(false);
      setVisible(false);
      if (showTimerRef.current != null) {
        window.clearTimeout(showTimerRef.current);
        showTimerRef.current = null;
      }
      if (ceilingTimerRef.current != null) {
        window.clearTimeout(ceilingTimerRef.current);
        ceilingTimerRef.current = null;
      }
    }

    // Popstate (browser back/forward) also triggers a nav that we want to cover.
    function handlePopState() {
      beginNav();
    }

    document.addEventListener("click", handleClick, true);
    window.addEventListener("popstate", handlePopState);
    return () => {
      document.removeEventListener("click", handleClick, true);
      window.removeEventListener("popstate", handlePopState);
      if (showTimerRef.current != null) window.clearTimeout(showTimerRef.current);
      if (ceilingTimerRef.current != null) window.clearTimeout(ceilingTimerRef.current);
    };
  }, []);

  // ── Finish: any pathname/query change = the new route has rendered ────────
  useEffect(() => {
    if (!pending) return;
    setPending(false);
    setVisible(false);
    if (showTimerRef.current != null) {
      window.clearTimeout(showTimerRef.current);
      showTimerRef.current = null;
    }
    if (ceilingTimerRef.current != null) {
      window.clearTimeout(ceilingTimerRef.current);
      ceilingTimerRef.current = null;
    }
    // `pending` intentionally omitted — we only care about route changes here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, searchParams]);

  if (!visible) return null;
  return <ViltrumLoader variant="fullscreen" />;
}
