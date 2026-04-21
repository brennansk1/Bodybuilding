"use client";

import { useEffect } from "react";
import { X } from "./icons";

export interface MobileCardDrawerItem {
  key: string;
  label: string;
  visible: boolean;
}

interface MobileCardDrawerProps {
  open: boolean;
  onClose: () => void;
  items: MobileCardDrawerItem[];
  onToggle: (key: string, next: boolean) => void;
  onReorder?: (keys: string[]) => void;
  title?: string;
}

/**
 * Bottom-sheet drawer for toggling/reordering dashboard widgets on mobile.
 *
 * Desktop already has an edit-mode grid powered by @dnd-kit, but that UX
 * doesn't translate to touch. This drawer gives mobile users a simple
 * checkbox list + move-up/down controls that write back to the same
 * preferences shape (`dashboard_settings.viz` / `.order`).
 */
export default function MobileCardDrawer({
  open,
  onClose,
  items,
  onToggle,
  onReorder,
  title = "Edit dashboard",
}: MobileCardDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  const move = (idx: number, dir: -1 | 1) => {
    if (!onReorder) return;
    const next = [...items];
    const target = idx + dir;
    if (target < 0 || target >= next.length) return;
    [next[idx], next[target]] = [next[target], next[idx]];
    onReorder(next.map((i) => i.key));
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-[90] flex flex-col justify-end bg-viltrum-obsidian/40 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-t-[16px] border-t border-viltrum-ash max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-viltrum-ash">
          <h2 className="h-card">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-viltrum-travertine hover:text-viltrum-obsidian"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="overflow-y-auto p-2">
          {items.map((item, idx) => (
            <div
              key={item.key}
              className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-card hover:bg-viltrum-limestone"
            >
              <label className="flex items-center gap-3 flex-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={item.visible}
                  onChange={(e) => onToggle(item.key, e.target.checked)}
                  className="w-4 h-4 accent-viltrum-obsidian"
                />
                <span className="text-[14px] text-viltrum-obsidian">{item.label}</span>
              </label>
              {onReorder && (
                <div className="flex items-center gap-1 text-viltrum-travertine">
                  <button
                    onClick={() => move(idx, -1)}
                    aria-label={`Move ${item.label} up`}
                    className="p-1 hover:text-viltrum-obsidian disabled:opacity-30"
                    disabled={idx === 0}
                  >
                    ↑
                  </button>
                  <button
                    onClick={() => move(idx, 1)}
                    aria-label={`Move ${item.label} down`}
                    className="p-1 hover:text-viltrum-obsidian disabled:opacity-30"
                    disabled={idx === items.length - 1}
                  >
                    ↓
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-viltrum-ash">
          <button onClick={onClose} className="btn-primary w-full">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
