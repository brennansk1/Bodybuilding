"use client";

import Image from "next/image";

/**
 * Full-screen Viltrum loading state — the logo pulses over a marble sheet
 * while the motto reveals. Used by `app/loading.tsx` suspense fallbacks.
 */
export default function ViltrumLoader({
  variant = "fullscreen",
}: {
  variant?: "fullscreen" | "inline";
}) {
  const outerClass =
    variant === "fullscreen"
      ? "fixed inset-0 z-[60] flex items-center justify-center bg-viltrum-marble"
      : "w-full py-16 flex items-center justify-center";

  return (
    <div className={outerClass} role="status" aria-live="polite" aria-label="Loading">
      <div className="flex flex-col items-center gap-6 select-none">
        <div className="relative w-20 h-20 viltrum-loader-mark">
          <Image
            src="/viltrum-logo.png"
            alt=""
            width={80}
            height={80}
            priority
            className="block"
          />
          {/* Rotating ring anchored to the mark */}
          <span
            aria-hidden="true"
            className="absolute inset-[-6px] rounded-full border border-viltrum-ash viltrum-loader-ring"
          />
        </div>
        <div className="flex flex-col items-center">
          <span className="font-display uppercase tracking-[6px] text-[22px] text-viltrum-obsidian">
            VILTRUM
          </span>
          <span className="font-display uppercase tracking-[4px] text-[10px] text-viltrum-travertine mt-1 viltrum-loader-motto">
            All Is Ours
          </span>
        </div>
      </div>

      <style jsx>{`
        .viltrum-loader-mark {
          animation: viltrum-pulse 1.6s ease-in-out infinite;
        }
        .viltrum-loader-ring {
          animation: viltrum-spin 2.4s linear infinite;
          border-top-color: var(--viltrum-accent);
        }
        .viltrum-loader-motto {
          animation: viltrum-motto 2.2s ease-in-out infinite;
        }
        @keyframes viltrum-pulse {
          0%, 100% { transform: scale(1); filter: drop-shadow(0 4px 8px rgba(196,64,64,0.25)); }
          50%      { transform: scale(1.06); filter: drop-shadow(0 6px 14px rgba(196,64,64,0.35)); }
        }
        @keyframes viltrum-spin {
          0%   { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes viltrum-motto {
          0%, 100% { opacity: 0.5; letter-spacing: 4px; }
          50%      { opacity: 1;   letter-spacing: 6px; }
        }
        @media (prefers-reduced-motion: reduce) {
          .viltrum-loader-mark, .viltrum-loader-ring, .viltrum-loader-motto {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
