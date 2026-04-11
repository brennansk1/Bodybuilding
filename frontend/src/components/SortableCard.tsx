"use client";

import { ReactNode } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

interface SortableCardProps {
  id: string;
  label: string;
  editMode: boolean;
  /** Legacy prop — DOM order now comes from `cardOrder` iteration. Accepted but unused. */
  orderIndex?: number;
  onHide?: () => void;
  children: ReactNode;
}

export default function SortableCard({
  id,
  label,
  editMode,
  onHide,
  children,
}: SortableCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
    disabled: !editMode,
  });

  const style: React.CSSProperties = {
    transform: editMode ? CSS.Transform.toString(transform) : undefined,
    transition: editMode ? transition : undefined,
    opacity: isDragging ? 0.5 : 1,
    position: "relative",
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-card-id={id}
      className="break-inside-avoid mb-4 sm:mb-6"
    >
      {editMode && (
        <>
          <div className="absolute inset-0 z-10 border-2 border-dashed border-jungle-accent/40 rounded-2xl pointer-events-none" />
          <button
            type="button"
            {...listeners}
            {...attributes}
            className="absolute top-2 left-2 z-20 px-2 py-1 bg-jungle-deeper/90 border border-jungle-border rounded-md text-[10px] text-jungle-muted hover:text-jungle-accent hover:border-jungle-accent cursor-grab active:cursor-grabbing"
            aria-label={`Drag ${label} card`}
          >
            ☰ {label}
          </button>
          {onHide && (
            <button
              type="button"
              onClick={onHide}
              className="absolute top-2 right-2 z-20 w-6 h-6 bg-red-500/20 hover:bg-red-500/40 border border-red-500/40 rounded-md text-red-400 text-xs font-bold flex items-center justify-center"
              aria-label={`Hide ${label}`}
            >
              ×
            </button>
          )}
        </>
      )}
      {children}
    </div>
  );
}
