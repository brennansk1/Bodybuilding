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
  success: "bg-green-500/10 border-green-500/25 text-green-400",
  error: "bg-red-500/10 border-red-500/25 text-red-400",
  warning: "bg-yellow-500/10 border-yellow-500/25 text-yellow-400",
  info: "bg-jungle-card/90 border-jungle-border/50 text-jungle-muted",
};

const TYPE_ICONS: Record<ToastType, string> = {
  success: "M5 13l4 4L19 7",
  error: "M6 18L18 6M6 6l12 12",
  warning: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z",
  info: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
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
    <div className="fixed top-16 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-center gap-2.5 px-4 py-3 rounded-xl border backdrop-blur-lg text-sm shadow-xl shadow-viltrum-obsidian/10 ${TYPE_STYLES[toast.type]}`}
          style={{ animation: "fadeScale 0.2s ease-out" }}
        >
          <svg className="w-4 h-4 shrink-0 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={TYPE_ICONS[toast.type]} />
          </svg>
          <span className="leading-snug">{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
