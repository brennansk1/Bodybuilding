"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface ExerciseOption {
  id: string;
  name: string;
  primary_muscle: string;
  secondary_muscles: string[];
  movement_type: string;
  equipment: string;
  compound: boolean;
}

interface ExerciseSwapModalProps {
  sessionId: string;
  oldExerciseId: string;
  oldExerciseName: string;
  primaryMuscle: string;
  onClose: () => void;
  onSwapped: (result: { sets_updated: number; auto_disliked: boolean }) => void;
}

export default function ExerciseSwapModal({
  sessionId,
  oldExerciseId,
  oldExerciseName,
  primaryMuscle,
  onClose,
  onSwapped,
}: ExerciseSwapModalProps) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<ExerciseOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [swapping, setSwapping] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Initial fetch: same primary muscle
  useEffect(() => {
    setLoading(true);
    api.get<ExerciseOption[]>(
      `/engine2/exercises/search?muscle=${encodeURIComponent(primaryMuscle)}`,
    )
      .then((res) => setOptions(res.filter((e) => e.id !== oldExerciseId)))
      .catch(() => setOptions([]))
      .finally(() => setLoading(false));
  }, [primaryMuscle, oldExerciseId]);

  // Client-side filter by query
  const filtered = query.trim()
    ? options.filter((o) =>
        o.name.toLowerCase().includes(query.toLowerCase()),
      )
    : options;

  const submit = async () => {
    if (!selectedId) return;
    setSwapping(true);
    try {
      const result = await api.post<{
        message: string;
        sets_updated: number;
        auto_disliked: boolean;
      }>(`/engine2/session/${sessionId}/swap-exercise`, {
        old_exercise_id: oldExerciseId,
        new_exercise_id: selectedId,
      });
      onSwapped({
        sets_updated: result.sets_updated,
        auto_disliked: result.auto_disliked,
      });
    } finally {
      setSwapping(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] bg-viltrum-obsidian/45 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        className="bg-jungle-card border border-jungle-border rounded-t-2xl sm:rounded-2xl w-full sm:max-w-md max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-jungle-border">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-bold text-jungle-text uppercase tracking-wider">Swap Exercise</h2>
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-full bg-jungle-deeper border border-jungle-border text-jungle-muted hover:text-jungle-accent flex items-center justify-center text-xs"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <p className="text-[11px] text-jungle-dim">
            Replacing <span className="text-jungle-muted font-medium">{oldExerciseName}</span> —
            same muscle group, matches your equipment.
          </p>
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search…"
          className="input-field m-4 mb-0"
          autoFocus
        />

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <p className="text-center text-xs text-jungle-dim py-4">Loading…</p>
          )}
          {!loading && filtered.length === 0 && (
            <p className="text-center text-xs text-jungle-dim py-4">
              No alternative exercises found for {primaryMuscle.replace(/_/g, " ")}.
            </p>
          )}
          {filtered.map((e) => (
            <button
              key={e.id}
              onClick={() => setSelectedId(e.id)}
              className={`w-full text-left p-3 rounded-xl border transition-colors ${
                selectedId === e.id
                  ? "bg-jungle-accent/15 border-jungle-accent text-jungle-text"
                  : "bg-jungle-deeper border-jungle-border text-jungle-muted hover:border-jungle-accent/50"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-medium">{e.name}</span>
                {e.compound && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-jungle-accent/15 text-jungle-accent uppercase font-semibold">
                    Compound
                  </span>
                )}
              </div>
              <div className="text-[10px] text-jungle-dim mt-0.5 flex gap-2">
                <span>{e.equipment.replace(/_/g, " ")}</span>
                <span>·</span>
                <span>{(e.movement_type || "").replace(/_/g, " ")}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-jungle-border flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-jungle-deeper border border-jungle-border text-jungle-muted"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!selectedId || swapping}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-jungle-accent text-white disabled:opacity-50 active:scale-95"
          >
            {swapping ? "Swapping…" : "Swap"}
          </button>
        </div>
      </div>
    </div>
  );
}
