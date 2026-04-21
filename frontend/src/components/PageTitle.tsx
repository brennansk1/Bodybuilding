"use client";

import { ReactNode } from "react";
import TegakiTitle from "./TegakiTitle";

interface PageTitleProps {
  /** Plain text headline. Required so Tegaki has something to animate. */
  text: string;
  /** Optional supporting text — rendered below in Crimson Pro. */
  subtitle?: ReactNode;
  /** Optional trailing content aligned to the right (buttons, badges). */
  actions?: ReactNode;
  /** Disable tegaki animation entirely for this page title. */
  static_?: boolean;
  className?: string;
}

export default function PageTitle({
  text,
  subtitle,
  actions,
  static_,
  className = "",
}: PageTitleProps) {
  return (
    <header
      className={`flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6 ${className}`.trim()}
    >
      <div className="flex flex-col gap-1">
        {static_ ? (
          <h1 className="h-display-lg">{text}</h1>
        ) : (
          <TegakiTitle text={text} as="h1" size="display-lg" />
        )}
        {subtitle && <p className="body-serif-sm max-w-xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
