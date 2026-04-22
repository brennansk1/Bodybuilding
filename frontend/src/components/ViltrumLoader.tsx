"use client";

import Image from "next/image";

/**
 * Viltrum loading state — the logo mark itself rotates. A faint concentric
 * ring pulses behind it (stationary) to read as a "chamber" the mark spins
 * inside. The motto below reveals on a slower cycle.
 *
 * - `fullscreen` — route-level Suspense fallback (used by `app/loading.tsx`).
 * - `inline`     — data-fetch placeholder inside a page.
 * - `compact`    — 28px mark for buttons / tight rows.
 *
 * Respects `prefers-reduced-motion`.
 */
export default function ViltrumLoader({
  variant = "fullscreen",
  label,
}: {
  variant?: "fullscreen" | "inline" | "compact";
  /** Override the accessible label. Default: "Loading". */
  label?: string;
}) {
  if (variant === "compact") {
    return (
      <span
        role="status"
        aria-label={label ?? "Loading"}
        className="inline-flex items-center justify-center"
      >
        <span className="relative w-7 h-7 inline-block">
          <Image
            src="/viltrum-logo.png"
            alt=""
            width={28}
            height={28}
            priority
            className="block viltrum-loader-mark-spin"
          />
        </span>
        <style jsx>{`
          .viltrum-loader-mark-spin {
            animation: viltrum-mark-spin 1.6s linear infinite;
            transform-origin: 50% 50%;
          }
          @keyframes viltrum-mark-spin {
            0%   { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          @media (prefers-reduced-motion: reduce) {
            .viltrum-loader-mark-spin { animation: none; }
          }
        `}</style>
      </span>
    );
  }

  const outerClass =
    variant === "fullscreen"
      ? "fixed inset-0 z-[60] flex items-center justify-center bg-viltrum-marble"
      : "w-full py-16 flex items-center justify-center";

  return (
    <div className={outerClass} role="status" aria-live="polite" aria-label={label ?? "Loading"}>
      <div className="flex flex-col items-center gap-6 select-none">
        {/* Spinning mark — the logo png rotates around its own center while a
            soft halo breathes behind it. The two motions run at different
            tempos so the composite feels mechanical, not hypnotic. */}
        <div className="relative w-24 h-24 flex items-center justify-center">
          <span aria-hidden className="absolute inset-0 rounded-full viltrum-loader-halo" />
          <Image
            src="/viltrum-logo.png"
            alt=""
            width={88}
            height={88}
            priority
            className="block relative viltrum-loader-mark"
          />
        </div>

        <div className="flex flex-col items-center">
          <span className="font-display uppercase tracking-[6px] text-[22px] text-viltrum-obsidian">
            VILTRUM
          </span>
          <span className="font-display uppercase tracking-[4px] text-[10px] text-viltrum-travertine mt-1 viltrum-loader-motto">
            {label ?? "All Is Ours"}
          </span>
        </div>
      </div>

      <style jsx>{`
        .viltrum-loader-mark {
          animation: viltrum-mark-spin 2s cubic-bezier(0.5, 0.05, 0.2, 0.95) infinite;
          transform-origin: 50% 50%;
          filter: drop-shadow(0 4px 10px rgba(196, 64, 64, 0.22));
          will-change: transform;
        }
        .viltrum-loader-halo {
          background: radial-gradient(
            closest-side,
            rgba(196, 64, 64, 0.18) 0%,
            rgba(196, 64, 64, 0.08) 55%,
            rgba(196, 64, 64, 0) 72%
          );
          animation: viltrum-halo 2.4s ease-in-out infinite;
        }
        .viltrum-loader-motto {
          animation: viltrum-motto 2.4s ease-in-out infinite;
        }
        /* Easing the rotation with a custom cubic gives a faint "cog tick"
           feel — the mark accelerates through the front half and steadies on
           the return, rather than the dead-flat linear spin of a generic
           spinner. */
        @keyframes viltrum-mark-spin {
          0%   { transform: rotate(0deg)   scale(1); }
          50%  { transform: rotate(180deg) scale(1.04); }
          100% { transform: rotate(360deg) scale(1); }
        }
        @keyframes viltrum-halo {
          0%, 100% { opacity: 0.55; transform: scale(0.96); }
          50%      { opacity: 1;    transform: scale(1.08); }
        }
        @keyframes viltrum-motto {
          0%, 100% { opacity: 0.5; letter-spacing: 4px; }
          50%      { opacity: 1;   letter-spacing: 6px; }
        }
        @media (prefers-reduced-motion: reduce) {
          .viltrum-loader-mark,
          .viltrum-loader-halo,
          .viltrum-loader-motto {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
