"use client";

import Image from "next/image";

type LogoVariant = "mark" | "lockup" | "splash";
type LogoSize = "sm" | "md" | "lg" | "xl" | "navbar";
type LogoTone = "ink" | "light";

interface LogoProps {
  /**
   * `mark` = icon only
   * `lockup` = icon + VILTRUM wordmark (default)
   * `splash` = icon + wordmark + "ALL IS OURS" tagline
   */
  variant?: LogoVariant;
  size?: LogoSize;
  /** `ink` (default) uses obsidian text on light bg. `light` uses white text — use on dark/accent surfaces. */
  tone?: LogoTone;
  /** Legacy alias for variant="splash". */
  showTagline?: boolean;
  className?: string;
}

const ICON_PX: Record<LogoSize, number> = { sm: 28, md: 36, lg: 56, xl: 96, navbar: 64 };
const WORDMARK_SIZE: Record<LogoSize, string> = {
  sm:     "text-[18px] tracking-[4px]",
  md:     "text-[24px] tracking-[6px]",
  lg:     "text-[36px] tracking-[8px]",
  xl:     "text-[56px] tracking-[10px]",
  navbar: "text-[26px] sm:text-[30px] tracking-[6px]",
};
const TAGLINE_SIZE: Record<LogoSize, string> = {
  sm:     "text-[9px] tracking-[4px]",
  md:     "text-[10px] tracking-[5px]",
  lg:     "text-[12px] tracking-[6px]",
  xl:     "text-[14px] tracking-[7px]",
  navbar: "text-[10px] tracking-[5px]",
};
const GAP: Record<LogoSize, string> = { sm: "gap-2", md: "gap-3", lg: "gap-4", xl: "gap-5", navbar: "gap-3" };

export default function Logo({
  variant,
  size = "md",
  tone = "ink",
  showTagline,
  className = "",
}: LogoProps) {
  // Resolve variant with legacy `showTagline` alias.
  const resolvedVariant: LogoVariant = variant ?? (showTagline ? "splash" : "lockup");
  const iconPx = ICON_PX[size];
  const wordmark = WORDMARK_SIZE[size];
  const tagline = TAGLINE_SIZE[size];
  const inkClass = tone === "light" ? "text-white" : "text-viltrum-obsidian";
  const taglineClass = tone === "light" ? "text-white/60" : "text-viltrum-travertine";

  return (
    <div
      className={`inline-flex flex-col items-center ${className}`.trim()}
      aria-label="Viltrum"
    >
      <div className={`inline-flex items-center ${GAP[size]}`}>
        <Image
          src="/viltrum-logo.png"
          alt=""
          width={iconPx}
          height={iconPx}
          priority
          className="block"
        />
        {resolvedVariant !== "mark" && (
          <span
            className={`font-display uppercase ${wordmark} ${inkClass}`}
            style={{ lineHeight: 1 }}
          >
            VILTRUM
          </span>
        )}
      </div>
      {resolvedVariant === "splash" && (
        <p
          className={`font-display uppercase mt-2 ${tagline} ${taglineClass}`}
          style={{ lineHeight: 1 }}
        >
          All Is Ours
        </p>
      )}
    </div>
  );
}
