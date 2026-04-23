"use client";

/**
 * V3.P8 — Progress Photo Stack.
 *
 * Pose-aware progress photos with horizontal timeline + overlay comparison.
 * Upload flow requires a pose type so the overlay aligns like-for-like shots
 * (front dbl biceps vs front dbl biceps, not front dbl biceps vs side chest).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { showToast } from "./Toast";

interface ProgressPhoto {
  id: string;
  photo_date: string;
  pose_type: string;
  storage_url: string;
  notes: string | null;
}

const POSE_LABELS: Record<string, string> = {
  front_relaxed:       "Front Relaxed",
  front_dbl_biceps:    "Front Double Biceps",
  side_chest_left:     "Side Chest (L)",
  side_chest_right:    "Side Chest (R)",
  back_dbl_biceps:     "Back Double Biceps",
  back_lat_spread:     "Back Lat Spread",
  abs_thigh:           "Abs & Thigh",
  side_triceps_left:   "Side Triceps (L)",
  side_triceps_right:  "Side Triceps (R)",
  most_muscular:       "Most Muscular",
  free_form:           "Free Form",
};

export default function ProgressPhotoStack() {
  const [photos, setPhotos] = useState<ProgressPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [poseFilter, setPoseFilter] = useState<string>("front_dbl_biceps");
  const [uploading, setUploading] = useState(false);
  const [compareA, setCompareA] = useState<ProgressPhoto | null>(null);
  const [compareB, setCompareB] = useState<ProgressPhoto | null>(null);
  const [overlay, setOverlay] = useState(0.5); // 0 = only A, 1 = only B
  const [showOverlayModal, setShowOverlayModal] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const uploadPose = useRef<string>("front_dbl_biceps");
  const uploadDate = useRef<string>(new Date().toISOString().slice(0, 10));

  const refresh = () => {
    setLoading(true);
    api.get<ProgressPhoto[]>("/progress/photos")
      .then(setPhotos)
      .catch(() => setPhotos([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const filtered = useMemo(
    () => photos.filter((p) => p.pose_type === poseFilter).sort((a, b) => a.photo_date.localeCompare(b.photo_date)),
    [photos, poseFilter]
  );

  const onFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("photo_date", uploadDate.current);
      form.append("pose_type", uploadPose.current);
      await api.postFormData("/progress/photos", form);
      showToast("Photo uploaded", "success");
      refresh();
    } catch (err) {
      showToast("Upload failed", "error");
      console.error(err);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="card space-y-4">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <div>
          <h3 className="h-card text-obsidian">Progress Photo Stack</h3>
          <p className="text-[11px] body-serif-sm italic text-iron leading-snug mt-0.5">
            Weekly photo in the same pose, same lighting. Slide to overlay past vs. present.
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={poseFilter}
            onChange={(e) => setPoseFilter(e.target.value)}
            className="input-field text-xs py-1.5 px-2 bg-white"
          >
            {Object.entries(POSE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              uploadPose.current = poseFilter;
              uploadDate.current = new Date().toISOString().slice(0, 10);
              fileRef.current?.click();
            }}
            disabled={uploading}
            className="btn-secondary text-xs px-3 py-1.5"
          >
            {uploading ? "…" : "+ Add"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={onFileSelected}
          />
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-4 gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="aspect-[3/4] bg-ash rounded animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-10 border border-dashed border-ash rounded-button">
          <p className="text-sm text-travertine">No {POSE_LABELS[poseFilter]} photos yet.</p>
          <p className="text-[11px] text-iron body-serif-sm italic mt-1">
            Take a weekly shot in this pose — you&apos;ll see improvement in a month.
          </p>
        </div>
      ) : (
        <>
          {/* Horizontal timeline scroll */}
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
            {filtered.map((p) => {
              const isA = compareA?.id === p.id;
              const isB = compareB?.id === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    if (!compareA) setCompareA(p);
                    else if (!compareB && p.id !== compareA.id) setCompareB(p);
                    else if (isA) setCompareA(null);
                    else if (isB) setCompareB(null);
                    else setCompareB(p);
                  }}
                  className={`relative flex-shrink-0 rounded overflow-hidden border-2 transition-all ${
                    isA ? "border-adriatic ring-2 ring-adriatic/30"
                      : isB ? "border-aureus ring-2 ring-aureus/30"
                      : "border-ash hover:border-pewter"
                  }`}
                >
                  <img
                    src={p.storage_url}
                    alt={`${POSE_LABELS[p.pose_type]} on ${p.photo_date}`}
                    className="w-20 h-28 object-cover"
                  />
                  <div className="absolute bottom-0 inset-x-0 bg-obsidian/70 text-white text-[9px] py-0.5 text-center tabular-nums">
                    {p.photo_date.slice(5)}
                  </div>
                  {isA && <span className="absolute top-1 left-1 text-[9px] bg-adriatic text-white px-1 rounded">A</span>}
                  {isB && <span className="absolute top-1 left-1 text-[9px] bg-aureus text-white px-1 rounded">B</span>}
                </button>
              );
            })}
          </div>

          {/* Compare action */}
          {compareA && compareB && (
            <div className="flex items-center justify-between gap-3 pt-2 border-t border-ash">
              <p className="text-[11px] text-iron body-serif-sm italic">
                Comparing {compareA.photo_date} → {compareB.photo_date}
              </p>
              <button
                type="button"
                onClick={() => setShowOverlayModal(true)}
                className="btn-accent text-xs px-3 py-1.5"
              >
                Overlay →
              </button>
            </div>
          )}
        </>
      )}

      {/* Overlay modal */}
      {showOverlayModal && compareA && compareB && (
        <div
          className="fixed inset-0 z-[110] flex flex-col items-center justify-center p-4 bg-obsidian/85"
          onClick={() => setShowOverlayModal(false)}
        >
          <div
            className="relative max-w-xl w-full max-h-[85vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative rounded-card overflow-hidden bg-obsidian">
              <img
                src={compareA.storage_url}
                alt="Photo A"
                className="block w-full h-auto max-h-[70vh] object-contain"
              />
              <img
                src={compareB.storage_url}
                alt="Photo B"
                className="absolute inset-0 block w-full h-auto max-h-[70vh] object-contain transition-opacity"
                style={{ opacity: overlay }}
              />
            </div>

            <div className="mt-4 bg-white rounded-card p-4 space-y-3">
              <input
                type="range"
                min={0}
                max={100}
                value={overlay * 100}
                onChange={(e) => setOverlay(parseInt(e.target.value) / 100)}
                className="w-full accent-aureus"
              />
              <div className="flex items-baseline justify-between text-xs tabular-nums">
                <span className="text-adriatic font-semibold">A · {compareA.photo_date}</span>
                <span className="text-travertine">{Math.round((1 - overlay) * 100)}% / {Math.round(overlay * 100)}%</span>
                <span className="text-aureus font-semibold">B · {compareB.photo_date}</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setOverlay(0)} className="btn-secondary text-xs flex-1 py-1.5">Only A</button>
                <button onClick={() => setOverlay(0.5)} className="btn-secondary text-xs flex-1 py-1.5">50/50</button>
                <button onClick={() => setOverlay(1)} className="btn-secondary text-xs flex-1 py-1.5">Only B</button>
              </div>
              <button
                onClick={() => setShowOverlayModal(false)}
                className="w-full text-xs text-travertine hover:text-obsidian py-1"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
