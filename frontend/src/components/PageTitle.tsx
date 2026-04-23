"use client";

import { ReactNode } from "react";
import TegakiTitle from "./TegakiTitle";

interface PageTitleProps {
  /** Plain text headline. Required so Tegaki has something to animate. */
  text: string;
  /** Optional supporting text — rendered below in Crimson Pro. */
  subtitle?: ReactNode;
  /** Optional eyebrow — small uppercase label rendered above the title in
   * `legion` red, with a leading rule. Per Claude Design page-hero treatment. */
  eyebrow?: string;
  /** Optional trailing content aligned to the right (buttons, badges). */
  actions?: ReactNode;
  /** Disable tegaki animation entirely for this page title. */
  static_?: boolean;
  className?: string;
}

/**
 * Per Claude Design — page hero with:
 *   - Red `legion` eyebrow underline + label (optional, defaults derived from
 *     the title if not provided).
 *   - Tegaki / display-lg title (existing).
 *   - Roman double-rule under the hero — thick obsidian + hairline shadow.
 */
export default function PageTitle({
  text,
  subtitle,
  eyebrow,
  actions,
  static_,
  className = "",
}: PageTitleProps) {
  return (
    <header
      className={`relative flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-7 pb-4 ${className}`.trim()}
      style={{
        borderBottom: "2px solid var(--viltrum-obsidian)",
      }}
    >
      <div className="flex flex-col gap-1">
        {eyebrow && (
          <div
            className="inline-flex items-center gap-2 mb-1"
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "10px",
              letterSpacing: "3px",
              textTransform: "uppercase",
              color: "var(--viltrum-legion)",
              fontWeight: 400,
            }}
          >
            <span
              aria-hidden
              style={{
                display: "inline-block",
                width: "24px",
                height: "1px",
                background: "var(--viltrum-legion)",
              }}
            />
            {eyebrow}
          </div>
        )}
        {static_ ? (
          <h1 className="h-display-lg">{text}</h1>
        ) : (
          <TegakiTitle text={text} as="h1" size="display-lg" />
        )}
        {subtitle && <p className="body-serif-sm max-w-xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
      {/* Roman double-rule — hairline shadow below the main border */}
      <span
        aria-hidden
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: "-6px",
          height: "1px",
          background: "var(--viltrum-obsidian)",
          opacity: 0.25,
          pointerEvents: "none",
        }}
      />
    </header>
  );
}
