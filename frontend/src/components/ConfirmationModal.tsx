"use client";

import { ReactNode, useEffect, useRef } from "react";

interface ConfirmationModalProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  /** Label for the confirmation button. Defaults to "Confirm". */
  confirmLabel?: string;
  /** Label for the cancel button. Defaults to "Cancel". */
  cancelLabel?: string;
  /** `"destructive"` (default) renders the confirm button in legion red; `"neutral"` uses the obsidian primary style. */
  variant?: "destructive" | "neutral";
  onConfirm: () => void;
  onCancel: () => void;
  /** When true, the confirm button is disabled and shows a spinner. */
  loading?: boolean;
}

export default function ConfirmationModal({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "destructive",
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmationModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  // Focus the confirm button and wire up ESC-to-cancel while open.
  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, loading, onCancel]);

  if (!open) return null;

  const confirmClass = variant === "destructive" ? "btn-accent" : "btn-primary";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-viltrum-obsidian/40 backdrop-blur-[2px]"
      onClick={() => !loading && onCancel()}
    >
      <div
        className="w-full max-w-md bg-white rounded-card border border-viltrum-ash shadow-card p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-title" className="h-card mb-2">{title}</h2>
        {description && (
          <div className="body-serif-sm mt-3 mb-5">{description}</div>
        )}
        <div className="flex items-center justify-end gap-3 mt-6">
          <button
            type="button"
            className="btn-secondary"
            onClick={onCancel}
            disabled={loading}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={confirmClass}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
