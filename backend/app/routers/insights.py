from __future__ import annotations

"""V3 Insights router.

Surfaces derived data the dashboard and settings pages need:

    /api/v1/insights/tier-projection    — Tier timing across HIGH/MED/LOW adherence
    /api/v1/insights/sensitivity        — Ranked lever impact for this athlete
    /api/v1/insights/weight-trend       — 7d + 14d rolling avg + weekly rate-of-change
    /api/v1/insights/muscle-timeline    — Per-site tape time-series (52w default)
    /api/v1/insights/archive/cycles     — Prep-replay list of completed cycles
    /api/v1/insights/archive/cycle/{n}  — Full cycle reconstruction

All endpoints are read-only. Writes live in their owning domain routers
(ppm.py for checkpoints, upload.py for photos, etc.).
"""

import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.ppm_checkpoint import PPMCheckpoint
from app.models.measurement import BodyWeightLog, TapeMeasurement

from app.constants.competitive_tiers import CompetitiveTier, coerce_tier
from app.constants.weight_caps import lookup_weight_cap
from app.engines.engine1.readiness import (
    project_tier_timing_across_adherence,
    compute_achieved_tier,
    compute_normalized_ffmi,
)
from app.engines.engine1.aesthetic_vector import (
    compute_arm_calf_neck_parity,
    compute_chest_waist_ratio,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])


# ---------------------------------------------------------------------------
# /tier-projection — HIGH / MED / LOW adherence years-to-tier
# ---------------------------------------------------------------------------
@router.get("/tier-projection")
async def tier_projection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prof = (await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prof or not prof.target_tier:
        raise HTTPException(400, "PPM target_tier required")

    tier = coerce_tier(prof.target_tier)

    # Pull latest weight + BF for gap computation
    bw_row = (await db.execute(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == current_user.id)
        .order_by(desc(BodyWeightLog.recorded_date))
        .limit(1)
    )).scalar_one_or_none()
    bw_kg = float(bw_row.weight_kg) if bw_row else 0.0

    # Use manual BF if provided; otherwise skip — the projection is robust to
    # a wide range of starting values.
    bf_pct = float(prof.manual_body_fat_pct) if prof.manual_body_fat_pct else None

    weight_cap_kg = lookup_weight_cap(prof.height_cm, prof.division)
    current_metrics = {
        "body_weight_kg": bw_kg,
        "bf_pct": bf_pct,
    }

    projections = project_tier_timing_across_adherence(
        current_metrics=current_metrics,
        target_tier=tier,
        training_years=float(prof.training_experience_years or 0),
        training_status=prof.training_status or "natural",
        weight_cap_kg=weight_cap_kg,
        division=prof.division,
    )

    return {
        "target_tier": prof.target_tier,
        "target_tier_name": tier.name,
        "projections": projections,
    }


# ---------------------------------------------------------------------------
# /sensitivity — Ranked lever impact
# ---------------------------------------------------------------------------
@router.get("/sensitivity")
async def sensitivity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return ranked lever impact for this athlete. Static ranking derived
    from sim analysis (see `simulation-20260422/REPORT.md`), personalised
    by the athlete's current state. Not a per-user regression — it's a
    coaching card with evidence-backed priorities."""
    prof = (await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prof:
        raise HTTPException(404, "profile not found")

    bw_row = (await db.execute(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == current_user.id)
        .order_by(desc(BodyWeightLog.recorded_date))
        .limit(1)
    )).scalar_one_or_none()

    bf = float(prof.manual_body_fat_pct) if prof.manual_body_fat_pct else None

    levers: list[dict] = []
    # 1. Starting BF is the #1 lever when the athlete is above the divisional
    # offseason ceiling. Fades below the ceiling.
    #
    # V3 — if the user has manually overridden the nutrition mode (e.g. they
    # explicitly chose bulk while high-BF), don't tell them to cut. Soften to
    # an advisory risk callout — they made an informed choice and the engine
    # should respect it, but surface the tradeoff so they know what they're
    # paying for the choice.
    sex = (prof.sex or "male").lower()
    offseason_ceiling = 13.0 if sex == "male" else 22.0
    override = prof.nutrition_mode_override
    if bf and bf > offseason_ceiling:
        if override == "bulk":
            levers.append({
                "rank": 1,
                "lever": "starting_bodyfat",
                "label": "Bulking at high BF — watch trajectory",
                "impact": "very_high",
                "reason": (
                    f"You're at {bf:.1f}% BF (ceiling ~{offseason_ceiling:.0f}%) "
                    f"and chose to bulk. The engine respects that — but a surplus "
                    f"at this BF partitions more aggressively toward fat than lean "
                    f"tissue. Expect lower muscle-fraction of scale gains and a "
                    f"longer eventual cut to reach stage condition."
                ),
                "action": "Keep weekly rate ≤+0.3%/wk. If BF rises >3 pts, cut.",
            })
        elif override in ("maintain", "cut"):
            levers.append({
                "rank": 1,
                "lever": "starting_bodyfat",
                "label": f"Manually {override}ing at high BF — good call",
                "impact": "very_high",
                "reason": (
                    f"You're at {bf:.1f}% BF (ceiling ~{offseason_ceiling:.0f}%) "
                    f"and chose to {override}. This is what the sim points to — "
                    f"strip BF first, then accumulate."
                ),
                "action": f"Target {'−0.5 to −1.0' if override == 'cut' else '±0.1'}%/wk.",
            })
        else:
            levers.append({
                "rank": 1,
                "lever": "starting_bodyfat",
                "label": "Cut to offseason ceiling first",
                "impact": "very_high",
                "reason": (
                    f"You're at {bf:.1f}% BF; offseason ceiling for your division is "
                    f"~{offseason_ceiling:.0f}%. Until you're under, every lean-bulk "
                    f"cycle spends capacity fighting fat gain instead of building mass. "
                    f"Sim: ~12 months of tier timing on the table."
                ),
                "action": "Run ppm_pre_cut. Target −0.7% BW/week until BF ≤ ceiling.",
            })

    # 2. Training quality dominates nutrition adherence 3×
    levers.append({
        "rank": len(levers) + 1,
        "lever": "training_quality",
        "label": "Training intensity × programming",
        "impact": "high",
        "reason": (
            "Sim: training intensity × programming accounts for ~3.5 kg of the "
            "6 kg HIGH→LOW LBM gap — nutrition adherence only ~0.3 kg. Quality "
            "sessions with a real program dominate hitting macros exactly."
        ),
        "action": "Hit prescribed RIR/RPE. Don't miss heavy compounds.",
    })

    # 3. Illness weeks (derived from sleep/stress)
    levers.append({
        "rank": len(levers) + 1,
        "lever": "illness_prevention",
        "label": "Sleep + stress → illness frequency",
        "impact": "high",
        "reason": (
            "Sim LOW adherence lost 47 weeks to illness/life over 5 years vs. "
            "11 for HIGH. Sleep doesn't matter directly as much as it matters "
            "through illness frequency — fatigue compounds into lost months."
        ),
        "action": "Protect sleep (>7.5 h). Log HRV + resting HR when wearable lands.",
    })

    # 4. Structural specialization
    priority_muscles = prof.structural_priority_muscles or []
    if priority_muscles:
        levers.append({
            "rank": len(levers) + 1,
            "lever": "structural_specialization",
            "label": f"Persistent specialization: {', '.join(priority_muscles)}",
            "impact": "medium",
            "reason": (
                "Structural asymmetries don't close via generic programming. "
                "Your flagged priority muscles get persistent specialization "
                "volume regardless of PPM cycle focus."
            ),
            "action": "Honor the +15% weekly set bonus on priority sites.",
        })

    # 5. Nutrition adherence — real but lower-leverage
    levers.append({
        "rank": len(levers) + 1,
        "lever": "nutrition_adherence",
        "label": "Macro + kcal adherence",
        "impact": "medium",
        "reason": (
            "Symmetric near-maintenance dampens both surplus AND deficit, so "
            "kcal misses show up less than training misses. Still matters, "
            "but not the #1 knob — get training right first."
        ),
        "action": "Hit protein daily. Weekly kcal avg > perfect daily numbers.",
    })

    return {
        "levers": levers,
        "coaching_summary": (
            "Priority order is set by what the multi-year simulation shows "
            "actually moves the needle for you. Don't chase macros at the "
            "expense of session quality or sleep."
        ),
    }


# ---------------------------------------------------------------------------
# /weight-trend — 7d/14d rolling averages + weekly rate-of-change
# ---------------------------------------------------------------------------
@router.get("/weight-trend")
async def weight_trend(
    days: int = Query(90, ge=14, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cutoff = date.today() - timedelta(days=days)
    rows = (await db.execute(
        select(BodyWeightLog)
        .where(
            BodyWeightLog.user_id == current_user.id,
            BodyWeightLog.recorded_date >= cutoff,
        )
        .order_by(asc(BodyWeightLog.recorded_date))
    )).scalars().all()

    if not rows:
        return {
            "points": [],
            "smoothed_7d": [],
            "smoothed_14d": [],
            "weekly_rate_pct": None,
            "weekly_rate_kg": None,
            "direction": "unknown",
            "in_target_band": None,
        }

    points = [
        {"date": r.recorded_date.isoformat(), "weight_kg": round(float(r.weight_kg), 2)}
        for r in rows
    ]

    def _rolling(values: list[float], window: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(values)):
            lo = max(0, i - window + 1)
            win = values[lo : i + 1]
            out.append(round(sum(win) / len(win), 2) if win else None)
        return out

    raw = [p["weight_kg"] for p in points]
    sm7 = _rolling(raw, 7)
    sm14 = _rolling(raw, 14)

    # Weekly rate: slope of last 14d smoothed series
    weekly_rate_kg: float | None = None
    weekly_rate_pct: float | None = None
    if len(sm14) >= 14 and sm14[-14] is not None and sm14[-1] is not None:
        delta = sm14[-1] - sm14[-14]
        weekly_rate_kg = round(delta / 2.0, 2)  # 14 days = 2 weeks
        if sm14[-14] > 0:
            weekly_rate_pct = round((delta / sm14[-14]) * 100.0 / 2.0, 2)

    direction = "steady"
    if weekly_rate_pct is not None:
        if weekly_rate_pct < -0.15:
            direction = "cutting"
        elif weekly_rate_pct > 0.15:
            direction = "bulking"

    # 0.5–1.0% per week is the Helms-cited target band (absolute value)
    in_target_band = None
    if weekly_rate_pct is not None:
        abs_rate = abs(weekly_rate_pct)
        in_target_band = 0.5 <= abs_rate <= 1.0

    return {
        "points": points,
        "smoothed_7d": sm7,
        "smoothed_14d": sm14,
        "weekly_rate_kg": weekly_rate_kg,
        "weekly_rate_pct": weekly_rate_pct,
        "direction": direction,
        "in_target_band": in_target_band,
    }


# ---------------------------------------------------------------------------
# /muscle-timeline — per-site tape time-series
# ---------------------------------------------------------------------------
_SITE_COLUMNS = {
    "neck": "neck",
    "shoulders": "shoulders",
    "chest": "chest",
    "bicep_left": "left_bicep",
    "bicep_right": "right_bicep",
    "forearm_left": "left_forearm",
    "forearm_right": "right_forearm",
    "waist": "waist",
    "hips": "hips",
    "thigh_left": "left_thigh",
    "thigh_right": "right_thigh",
    "calf_left": "left_calf",
    "calf_right": "right_calf",
    "glutes": "glutes",
    "back_width": "back_width",
}


@router.get("/muscle-timeline/{site}")
async def muscle_timeline(
    site: str,
    weeks: int = Query(52, ge=4, le=260),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = _SITE_COLUMNS.get(site)
    if col is None:
        raise HTTPException(400, f"unknown site '{site}'")
    cutoff = date.today() - timedelta(weeks=weeks)

    rows = (await db.execute(
        select(TapeMeasurement)
        .where(
            TapeMeasurement.user_id == current_user.id,
            TapeMeasurement.recorded_date >= cutoff,
        )
        .order_by(asc(TapeMeasurement.recorded_date))
    )).scalars().all()

    series = []
    for r in rows:
        val = getattr(r, col, None)
        if val is None:
            continue
        series.append({
            "date": r.recorded_date.isoformat(),
            "value_cm": round(float(val), 1),
        })

    # Growth acceleration detection — find 4-week windows where the slope
    # is > 2× the global slope. Flag these for UI annotation.
    accel_windows: list[dict] = []
    if len(series) >= 8:
        values = [p["value_cm"] for p in series]
        global_slope = (values[-1] - values[0]) / max(1, len(values) - 1)
        if global_slope > 0:
            for i in range(len(values) - 4):
                window_slope = (values[i + 4] - values[i]) / 4.0
                if window_slope > 2.0 * global_slope:
                    accel_windows.append({
                        "start_date": series[i]["date"],
                        "end_date": series[i + 4]["date"],
                        "rate_vs_baseline": round(window_slope / global_slope, 2),
                    })

    return {
        "site": site,
        "series": series,
        "acceleration_windows": accel_windows,
    }


# ---------------------------------------------------------------------------
# /archive/cycles — Prep Replay list
# ---------------------------------------------------------------------------
@router.get("/archive/cycles")
async def archive_cycles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(PPMCheckpoint)
        .where(PPMCheckpoint.user_id == current_user.id)
        .order_by(asc(PPMCheckpoint.cycle_number))
    )).scalars().all()

    summaries = []
    for r in rows:
        summaries.append({
            "cycle_number": r.cycle_number,
            "checkpoint_date": r.checkpoint_date.isoformat() if r.checkpoint_date else None,
            "body_weight_kg": r.body_weight_kg,
            "bf_pct": r.bf_pct,
            "hqi_score": r.hqi_score,
            "readiness_state": r.readiness_state,
            "limiting_factor": r.limiting_factor,
            "cycle_focus": r.cycle_focus,
        })
    return {"cycles": summaries}


@router.get("/archive/cycle/{cycle_number}")
async def archive_cycle_detail(
    cycle_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(PPMCheckpoint)
        .where(
            PPMCheckpoint.user_id == current_user.id,
            PPMCheckpoint.cycle_number == cycle_number,
        )
        .order_by(desc(PPMCheckpoint.checkpoint_date))
        .limit(1)
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(404, f"cycle {cycle_number} not found")

    return {
        "cycle_number": row.cycle_number,
        "checkpoint_date": row.checkpoint_date.isoformat() if row.checkpoint_date else None,
        # V3 fix — frontend `CycleDetail` extends `CycleSummary`, so these
        # need to be top-level (not only nested in readiness) for the
        # archive page row rendering + comparison deltas.
        "body_weight_kg": row.body_weight_kg,
        "bf_pct": row.bf_pct,
        "hqi_score": row.hqi_score,
        "readiness_state": row.readiness_state,
        "readiness": {
            "state": row.readiness_state,
            "hqi_score": row.hqi_score,
            "ffmi": row.ffmi,
            "bf_pct": row.bf_pct,
            "weight_cap_pct": row.weight_cap_pct,
            "shoulder_waist_ratio": row.shoulder_waist_ratio,
            "chest_waist_ratio": row.chest_waist_ratio,
            "arm_calf_neck_parity": row.arm_calf_neck_parity,
            "illusion_xframe": row.illusion_xframe,
            "conditioning_pct": row.conditioning_pct,
        },
        "limiting_factor": row.limiting_factor,
        "cycle_focus": row.cycle_focus,
        "measurements": row.measurements_json,
        "macros_snapshot": row.macros_snapshot,
        "training_snapshot": row.training_snapshot,
        "volume_snapshot": row.volume_snapshot,
        "notes": row.notes,
    }
