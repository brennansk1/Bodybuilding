"use client";

import { useEffect, useState } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

let _toastId = 0;
type Listener = (toasts: Toast[]) => void;
let _toasts: Toast[] = [];
const _listeners: Set<Listener> = new Set();

function notify() {
  _listeners.forEach((l) => l([..._toasts]));
}

export function showToast(message: string, type: ToastType = "info", duration = 4000) {
  const id = ++_toastId;
  _toasts = [..._toasts, { id, message, type }];
  notify();
  setTimeout(() => {
    _toasts = _toasts.filter((t) => t.id !== id);
    notify();
  }, duration);
}

export function showError(message: string) {
  showToast(message, "error", 5000);
}

export function showSuccess(message: string) {
  showToast(message, "success", 3000);
}

const TYPE_STYLES: Record<ToastType, string> = {
  success: "bg-green-500/10 border-green-500/30 text-green-400",
  error: "bg-red-500/10 border-red-500/30 text-red-400",
  warning: "bg-yellow-500/10 border-yellow-500/30 text-yellow-400",
  info: "bg-jungle-deeper border-jungle-border text-jungle-muted",
};

const TYPE_ICONS: Record<ToastType, string> = {
  success: "✓",
  error: "✕",
  warning: "⚠",
  info: "ℹ",
};

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const listener: Listener = (t) => setToasts(t);
    _listeners.add(listener);
    return () => { _listeners.delete(listener); };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border text-sm shadow-lg animate-fade-in ${TYPE_STYLES[toast.type]}`}
        >
          <span className="shrink-0 font-bold text-base leading-tight">{TYPE_ICONS[toast.type]}</span>
          <span className="leading-snug">{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
