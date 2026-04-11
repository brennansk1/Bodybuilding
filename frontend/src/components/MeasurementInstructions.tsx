"use client";

import { useState } from "react";

export const MEASUREMENT_INSTRUCTIONS: Record<string, string> = {
  neck: "Below the larynx, tape perpendicular to the long axis of the neck. Shoulders relaxed, looking straight ahead.",
  shoulders: "Around the widest point of the deltoids. Arms relaxed at sides, tape parallel to the floor.",
  chest: "Relaxed, arms at sides. Tape level around the nipple line at the end of a normal exhale. Don't puff the chest.",
  chest_relaxed: "Lats fully relaxed (let the arms hang). Isolates the pec contribution to chest girth.",
  chest_lat_spread: "Lats flared out. Captures full torso including lat mass — compare against relaxed chest for V-taper.",
  back_width: "Linear breadth (not circumference) between the rear axillary folds. Use calipers or a straight ruler on photos.",
  left_bicep: "Arm flexed hard at 90°. Measure the peak of the biceps belly. Same arm position every week.",
  right_bicep: "Arm flexed hard at 90°. Measure the peak of the biceps belly. Same arm position every week.",
  left_forearm: "Arm extended, palm up, fist relaxed. Tape around the widest point (usually 1–2 inches below the elbow).",
  right_forearm: "Arm extended, palm up, fist relaxed. Tape around the widest point (usually 1–2 inches below the elbow).",
  waist: "Narrowest point above the navel at end of normal exhale. DO NOT suck in. Critical for physique tracking.",
  hips: "Feet together, tape around the widest part of the glutes. Keep tape level all the way around.",
  left_thigh: "Standing, weight even on both feet. Tape 1 inch below the glute fold, perpendicular to femur.",
  right_thigh: "Standing, weight even on both feet. Tape 1 inch below the glute fold, perpendicular to femur.",
  left_proximal_thigh: "Just below the glute fold — captures upper thigh / hip-tie-in mass.",
  right_proximal_thigh: "Just below the glute fold — captures upper thigh / hip-tie-in mass.",
  left_distal_thigh: "Just above the patella. Tracks VMO (teardrop) development.",
  right_distal_thigh: "Just above the patella. Tracks VMO (teardrop) development.",
  left_calf: "Standing, weight even, calf relaxed. Tape around the widest point of the gastrocnemius.",
  right_calf: "Standing, weight even, calf relaxed. Tape around the widest point of the gastrocnemius.",
  // Skinfolds
  "skinfold_chest": "Diagonal fold halfway between the anterior axillary line and the nipple (men) or 1/3 (women).",
  "skinfold_midaxillary": "Vertical fold on the midaxillary line at the level of the xiphoid process.",
  "skinfold_tricep": "Vertical fold on the posterior midline of the upper arm, halfway between acromion and olecranon. Arm relaxed.",
  "skinfold_subscapular": "Diagonal fold 1–2 cm below the inferior angle of the scapula, 45° to the spine.",
  "skinfold_abdominal": "Vertical fold 2 cm to the right of the umbilicus.",
  "skinfold_suprailiac": "Diagonal fold above the iliac crest at the anterior axillary line.",
  "skinfold_thigh": "Vertical fold on the anterior midline of the thigh, halfway between the inguinal crease and patella.",
  "skinfold_bicep": "Vertical fold on the anterior midline of the upper arm, over the biceps belly, arm relaxed.",
  "skinfold_lower_back": "Vertical fold 2 inches lateral to the spine at the level of the iliac crest.",
  "skinfold_calf": "Vertical fold on the medial aspect of the calf at max girth.",
};

interface Props {
  siteKey: string;
  label: string;
  className?: string;
}

export default function MeasurementInstructions({ siteKey, label, className = "" }: Props) {
  const [open, setOpen] = useState(false);
  const instruction = MEASUREMENT_INSTRUCTIONS[siteKey];

  return (
    <div className={`relative inline-flex items-center gap-1 ${className}`}>
      <span>{label}</span>
      {instruction && (
        <>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(!open);
            }}
            className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-jungle-border/60 text-[9px] text-jungle-dim hover:text-jungle-accent hover:border-jungle-accent/60 transition-colors"
            aria-label={`How to measure ${label}`}
          >
            i
          </button>
          {open && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setOpen(false)}
              />
              <div className="absolute left-0 top-5 z-50 w-56 p-2.5 rounded-lg bg-jungle-deeper border border-jungle-border shadow-xl text-[10px] leading-snug text-jungle-text">
                <div className="font-semibold text-jungle-accent mb-1">{label}</div>
                <div className="text-jungle-muted">{instruction}</div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
