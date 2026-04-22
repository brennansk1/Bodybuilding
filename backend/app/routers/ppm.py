from __future__ import annotations

"""
Perpetual Progression Mode (PPM) API

Provides threshold-gated competitive-tier readiness evaluation and 14-16
week improvement cycle planning that cleanly integrates with the existing
macro/meso/microcycle engines:

- Macrocycle: 14(-16)-week improvement cycle (this module)
- Mesocycle:  weeks 1-14 mapped to sub-phases via
              prep_timeline.ppm_phase_for_week + periodization.compute_cycle_mesocycle
- Microcycle: per-week per-muscle working-set targets (compute_cycle_mesocycle)
              + split rotation via periodization.generate_mesocycle / _SPLIT_TEMPLATES

All endpoints are Classic Physique-first; other divisions surface a
NotImplementedError that the API returns as a 501.
"""

import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.ppm_checkpoint import PPMCheckpoint
from app.models.measurement import BodyWeightLog, TapeMeasurement

from app.constants.competitive_tiers import (
    CompetitiveTier,
    ReadinessState,
    coerce_tier,
)
from app.constants.weight_caps import lookup_weight_cap
from app.engines.engine1.readiness import (
    compute_normalized_ffmi,
    evaluate_readiness,
    estimate_cycles_to_tier,
)
from app.engines.engine1.honesty import check_natural_attainability
from app.engines.engine1.aesthetic_vector import (
    compute_arm_calf_neck_parity,
    compute_chest_waist_ratio,
)
from app.engines.engine1.prep_timeline import (
    get_current_phase,
    ppm_phase_for_week,
)
from app.engines.engine2.periodization import compute_cycle_mesocycle
from app.engines.engine2.volume_landmarks import get_all_landmarks
from app.engines.engine3.macros import (
    compute_tdee,
    compute_macros,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ppm", tags=["ppm"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class AttainabilityRequest(BaseModel):
    target_tier: int = Field(..., ge=1, le=5)


class StartCycleRequest(BaseModel):
    target_tier: int | None = Field(None, ge=1, le=5)
    focus_muscles: list[str] | None = None   # overrides auto-detected limiter
    start_date: date | None = None           # defaults to today


class TransitionToCompRequest(BaseModel):
    competition_date: date


class CheckpointNotes(BaseModel):
    conditioning_style: Literal["full", "tight", "dry", "grainy"] | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Helpers — aggregate metrics from the existing engines
# ---------------------------------------------------------------------------
async def _latest_measurements(db: AsyncSession, user_id) -> tuple[dict, dict]:
    """Return (tape_dict_cm, bodyweight_dict) — empty dicts when absent."""
    tape_q = await db.execute(
        select(TapeMeasurement)
        .where(TapeMeasurement.user_id == user_id)
        .order_by(desc(TapeMeasurement.recorded_date))
        .limit(1)
    )
    tape = tape_q.scalar_one_or_none()

    bw_q = await db.execute(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == user_id)
        .order_by(desc(BodyWeightLog.recorded_date))
        .limit(1)
    )
    bw = bw_q.scalar_one_or_none()

    tape_dict: dict = {}
    if tape is not None:
        for field in (
            "neck", "shoulders", "chest",
            "left_bicep", "right_bicep",
            "left_forearm", "right_forearm",
            "waist", "hips",
            "left_thigh", "right_thigh",
            "left_calf", "right_calf",
        ):
            val = getattr(tape, field, None)
            if val is not None:
                tape_dict[field] = float(val)
        # Average L/R for convenience
        for pair, key in (
            (("left_bicep", "right_bicep"), "bicep"),
            (("left_forearm", "right_forearm"), "forearm"),
            (("left_thigh", "right_thigh"), "thigh"),
            (("left_calf", "right_calf"), "calf"),
        ):
            lv = tape_dict.get(pair[0])
            rv = tape_dict.get(pair[1])
            if lv is not None and rv is not None:
                tape_dict[key] = (lv + rv) / 2.0
            elif lv is not None:
                tape_dict[key] = lv
            elif rv is not None:
                tape_dict[key] = rv

    bw_dict: dict = {}
    if bw is not None:
        bw_dict["body_weight_kg"] = float(bw.weight_kg)
        # BodyWeightLog has no body_fat_pct column — BF% lives on SkinfoldMeasurement
        # or UserProfile.manual_body_fat_pct. Caller derives it downstream.

    return tape_dict, bw_dict


async def _compute_athlete_metrics(
    db: AsyncSession, user: User, profile: UserProfile
) -> dict:
    """Aggregate all metrics readiness.evaluate_readiness needs."""
    tape, bw = await _latest_measurements(db, user.id)

    body_weight_kg = bw.get("body_weight_kg") or 0.0
    bf_pct = bw.get("bf_pct") or profile.manual_body_fat_pct or 15.0
    lbm_kg = body_weight_kg * (1.0 - bf_pct / 100.0)

    ffmi = compute_normalized_ffmi(lbm_kg, profile.height_cm) if profile.height_cm else 0.0

    # Proportions
    sw_ratio = 0.0
    cw_ratio = 0.0
    if tape.get("shoulders") and tape.get("waist"):
        sw_ratio = tape["shoulders"] / tape["waist"]
    if tape.get("chest") and tape.get("waist"):
        cw_ratio = compute_chest_waist_ratio(tape["chest"], tape["waist"])

    parity = compute_arm_calf_neck_parity(tape)
    parity_diff_in = parity.get("max_diff_inches") or 99.0

    # HQI — fetch latest diagnostic if present, with an age for the staleness
    # guard in readiness.evaluate_readiness.
    from datetime import datetime, timezone
    from app.models.diagnostic import HQILog
    hqi_q = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.created_at)).limit(1)
    )
    hqi_row = hqi_q.scalar_one_or_none()
    hqi_score = float(hqi_row.overall_hqi) if hqi_row and hqi_row.overall_hqi is not None else 0.0
    hqi_age_days: int | None = None
    if hqi_row is not None:
        created = getattr(hqi_row, "created_at", None) or getattr(hqi_row, "recorded_date", None)
        if created is not None:
            ref = datetime.now(timezone.utc) if hasattr(created, "tzinfo") else datetime.utcnow()
            try:
                hqi_age_days = int((ref - created).days) if hasattr(created, "year") else None
            except (TypeError, ValueError):
                hqi_age_days = None

    return {
        "body_weight_kg": body_weight_kg,
        "bf_pct": bf_pct,
        "lbm_kg": lbm_kg,
        "normalized_ffmi": ffmi,
        "shoulder_waist_ratio": sw_ratio,
        "chest_waist_ratio": cw_ratio,
        "arm_calf_neck_max_diff_inches": parity_diff_in,
        "arm_calf_neck_parity": parity,
        "hqi_score": hqi_score,
        "hqi_age_days": hqi_age_days,
        "training_years": float(profile.training_experience_years or 0),
    }


def _limiting_muscles_from_readiness(readiness: dict, tape: dict) -> list[str]:
    """Translate a limiting factor into specific muscle groups for specialization."""
    limiter = readiness.get("limiting_factor")
    mapping = {
        "shoulder_waist":       ["side_delt", "back"],
        "chest_waist":          ["chest", "back"],
        "arm_calf_neck_parity": [],    # resolved below from parity values
        "weight_cap_pct":       [],    # overall mass — no specialization
        "ffmi":                 [],    # overall mass
        "hqi":                  [],    # handled downstream via muscle_gaps
    }
    muscles = list(mapping.get(limiter, []))

    if limiter == "arm_calf_neck_parity":
        # Grow whichever of arm/calf/neck is smallest.
        arm = tape.get("bicep", 0)
        calf = tape.get("calf", 0)
        neck = tape.get("neck", 0)
        smallest = min([("biceps", arm), ("calves", calf), ("traps", neck)], key=lambda x: x[1] or 99)
        muscles = [smallest[0]]

    return muscles


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------
@router.get("/status")
async def get_ppm_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return PPM state (enabled / target tier / current cycle progress)."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, "Profile not found.")

    today = date.today()
    current_week = prof.current_cycle_week
    if prof.ppm_enabled and prof.current_cycle_start_date:
        delta = (today - prof.current_cycle_start_date).days
        current_week = max(1, (delta // 7) + 1)

    return {
        "ppm_enabled": prof.ppm_enabled,
        "target_tier": prof.target_tier,
        "training_status": prof.training_status,
        "current_cycle_number": prof.current_cycle_number,
        "current_cycle_start_date": prof.current_cycle_start_date.isoformat() if prof.current_cycle_start_date else None,
        "current_cycle_week": current_week,
        "cycle_focus_muscles": prof.cycle_focus_muscles,
        "competition_date": prof.competition_date.isoformat() if prof.competition_date else None,
        "current_phase": get_current_phase(
            competition_date=prof.competition_date,
            current_date=today,
            ppm_enabled=prof.ppm_enabled,
            cycle_start_date=prof.current_cycle_start_date,
        ),
    }


@router.post("/evaluate")
async def evaluate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate current readiness against the athlete's target tier."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, "Profile not found.")
    if prof.target_tier is None:
        raise HTTPException(400, "Select a target_tier before evaluating readiness.")

    try:
        cap_kg = lookup_weight_cap(prof.height_cm, prof.division)
        metrics = await _compute_athlete_metrics(db, user, prof)
        readiness = evaluate_readiness(
            metrics,
            target_tier=prof.target_tier,
            weight_cap_kg=cap_kg,
            training_status=prof.training_status,
            division=prof.division,
        )
        projection = estimate_cycles_to_tier(
            metrics,
            target_tier=prof.target_tier,
            training_years=metrics["training_years"],
            training_status=prof.training_status,
            weight_cap_kg=cap_kg,
            division=prof.division,
        )
        tape, _ = await _latest_measurements(db, user.id)
        return {
            "readiness": readiness,
            "projection": projection,
            "weight_cap_kg": cap_kg,
            "metrics_snapshot": {
                k: v for k, v in metrics.items()
                if k != "arm_calf_neck_parity"  # nested dict omitted
            },
            "tape": {
                "bicep":  tape.get("bicep"),
                "calf":   tape.get("calf"),
                "neck":   tape.get("neck"),
                "chest":  tape.get("chest"),
                "waist":  tape.get("waist"),
            },
        }
    except NotImplementedError as e:
        raise HTTPException(501, str(e))


@router.post("/attainability")
async def attainability(
    body: AttainabilityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the honesty gate — Casey Butt predicted max vs tier requirement.

    Required before enabling PPM at T3+ for natural athletes.
    """
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, "Profile not found.")
    try:
        result = check_natural_attainability(
            height_cm=prof.height_cm,
            wrist_cm=prof.wrist_circumference_cm,
            ankle_cm=prof.ankle_circumference_cm,
            target_tier=body.target_tier,
            division=prof.division,
        )
        return result
    except NotImplementedError as e:
        raise HTTPException(501, str(e))


@router.post("/start-cycle")
async def start_cycle(
    body: StartCycleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new improvement cycle and return the full 14-week plan."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, "Profile not found.")

    if prof.competition_date is not None:
        raise HTTPException(
            409,
            "A competition date is set — disable it or call /ppm/transition-to-comp first."
        )

    # Honesty gate for naturals aiming at T3+
    target = body.target_tier or prof.target_tier or 1
    if prof.training_status == "natural" and target >= 3:
        try:
            honesty = check_natural_attainability(
                height_cm=prof.height_cm,
                wrist_cm=prof.wrist_circumference_cm,
                ankle_cm=prof.ankle_circumference_cm,
                target_tier=target,
                division=prof.division,
            )
            if not honesty["overall_attainable"]:
                raise HTTPException(
                    409,
                    detail={
                        "error": "honesty_gate_blocked",
                        "attainability": honesty,
                        "hint": "Lower the tier or set training_status='enhanced' if applicable.",
                    },
                )
        except NotImplementedError as e:
            raise HTTPException(501, str(e))

    # Detect focus muscles from readiness.
    metrics = await _compute_athlete_metrics(db, user, prof)
    cap_kg = lookup_weight_cap(prof.height_cm, prof.division)
    readiness = evaluate_readiness(
        metrics, target, cap_kg, prof.training_status, prof.division
    )
    tape, _ = await _latest_measurements(db, user.id)
    auto_focus = _limiting_muscles_from_readiness(readiness, tape)
    focus_muscles = body.focus_muscles or auto_focus

    # Persist cycle state on profile.
    prof.ppm_enabled = True
    prof.target_tier = target
    prof.current_cycle_number = (prof.current_cycle_number or 0) + 1
    prof.current_cycle_start_date = body.start_date or date.today()
    prof.current_cycle_week = 1
    prof.cycle_focus_muscles = focus_muscles
    await db.flush()

    plan = _build_cycle_plan(
        prof=prof,
        metrics=metrics,
        focus_muscles=focus_muscles,
        mini_cut_active=(metrics["bf_pct"] > 15.0),
    )

    return {
        "cycle_number": prof.current_cycle_number,
        "target_tier": prof.target_tier,
        "focus_muscles": focus_muscles,
        "readiness_at_start": readiness,
        "plan": plan,
    }


@router.get("/plan/{week}")
async def get_week_plan(
    week: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return detailed training + macro plan for a specific cycle week."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None or not prof.ppm_enabled:
        raise HTTPException(404, "No active PPM cycle.")

    metrics = await _compute_athlete_metrics(db, user, prof)
    plan = _build_cycle_plan(
        prof=prof,
        metrics=metrics,
        focus_muscles=prof.cycle_focus_muscles or [],
        mini_cut_active=(metrics["bf_pct"] > 15.0),
    )
    week = max(1, min(week, len(plan["weeks"])))
    return {
        "cycle_number": prof.current_cycle_number,
        "week": week,
        "week_plan": plan["weeks"][week - 1],
        "cycle_summary": {
            "target_tier": prof.target_tier,
            "focus_muscles": plan["focus_muscles"],
            "split": plan["split"],
            "total_weeks": len(plan["weeks"]),
        },
    }


@router.post("/checkpoint")
async def post_checkpoint(
    body: CheckpointNotes,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a checkpoint row at cycle week 14 + return before/after diff."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None or not prof.ppm_enabled:
        raise HTTPException(404, "No active PPM cycle.")
    if prof.target_tier is None:
        raise HTTPException(400, "Select a target_tier before checkpointing.")

    metrics = await _compute_athlete_metrics(db, user, prof)
    cap_kg = lookup_weight_cap(prof.height_cm, prof.division)
    readiness = evaluate_readiness(
        metrics, prof.target_tier, cap_kg, prof.training_status, prof.division
    )

    # Persist the checkpoint row.
    row = PPMCheckpoint(
        user_id=user.id,
        cycle_number=prof.current_cycle_number,
        checkpoint_date=date.today(),
        body_weight_kg=metrics["body_weight_kg"],
        bf_pct=metrics["bf_pct"],
        ffmi=metrics["normalized_ffmi"],
        shoulder_waist_ratio=metrics["shoulder_waist_ratio"],
        chest_waist_ratio=metrics["chest_waist_ratio"],
        arm_calf_neck_parity=metrics["arm_calf_neck_max_diff_inches"],
        hqi_score=metrics["hqi_score"],
        weight_cap_pct=(metrics["body_weight_kg"] / cap_kg) if cap_kg else None,
        readiness_state=readiness["state"],
        limiting_factor=readiness.get("limiting_factor"),
        cycle_focus=",".join(prof.cycle_focus_muscles or []),
        measurements_json={
            "metrics": {k: v for k, v in metrics.items() if k != "arm_calf_neck_parity"},
            "arm_calf_neck_parity": metrics["arm_calf_neck_parity"],
            "conditioning_style": body.conditioning_style,
        },
        notes=body.notes,
    )
    db.add(row)
    await db.flush()

    # Find the previous checkpoint for delta display.
    prev_q = await db.execute(
        select(PPMCheckpoint)
        .where(PPMCheckpoint.user_id == user.id)
        .where(PPMCheckpoint.id != row.id)
        .order_by(desc(PPMCheckpoint.checkpoint_date))
        .limit(1)
    )
    prev = prev_q.scalar_one_or_none()
    delta = None
    if prev:
        delta = {
            "body_weight_kg": _round_delta(row.body_weight_kg, prev.body_weight_kg),
            "bf_pct": _round_delta(row.bf_pct, prev.bf_pct),
            "ffmi": _round_delta(row.ffmi, prev.ffmi),
            "shoulder_waist_ratio": _round_delta(row.shoulder_waist_ratio, prev.shoulder_waist_ratio),
            "chest_waist_ratio": _round_delta(row.chest_waist_ratio, prev.chest_waist_ratio),
            "arm_calf_neck_parity": _round_delta(row.arm_calf_neck_parity, prev.arm_calf_neck_parity),
            "hqi_score": _round_delta(row.hqi_score, prev.hqi_score),
        }

    return {
        "checkpoint_id": str(row.id),
        "cycle_number": row.cycle_number,
        "readiness": readiness,
        "delta_vs_last": delta,
        "recommended_next_focus": _limiting_muscles_from_readiness(
            readiness, (await _latest_measurements(db, user.id))[0]
        ),
    }


@router.get("/history")
async def history(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(PPMCheckpoint)
        .where(PPMCheckpoint.user_id == user.id)
        .order_by(desc(PPMCheckpoint.checkpoint_date))
        .limit(limit)
    )
    rows = q.scalars().all()
    return [
        {
            "id": str(r.id),
            "cycle_number": r.cycle_number,
            "checkpoint_date": r.checkpoint_date.isoformat(),
            "body_weight_kg": r.body_weight_kg,
            "bf_pct": r.bf_pct,
            "ffmi": r.ffmi,
            "shoulder_waist_ratio": r.shoulder_waist_ratio,
            "chest_waist_ratio": r.chest_waist_ratio,
            "arm_calf_neck_parity": r.arm_calf_neck_parity,
            "hqi_score": r.hqi_score,
            "weight_cap_pct": r.weight_cap_pct,
            "readiness_state": r.readiness_state,
            "limiting_factor": r.limiting_factor,
            "cycle_focus": r.cycle_focus,
        }
        for r in rows
    ]


@router.post("/transition-to-comp")
async def transition_to_comp(
    body: TransitionToCompRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable PPM and set a competition date, handing off to prep_timeline."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, "Profile not found.")

    prof.ppm_enabled = False
    prof.competition_date = body.competition_date
    prof.current_cycle_start_date = None
    prof.current_cycle_week = 1
    await db.flush()

    return {
        "message": "Switched to competition mode. Engines will now drive prep from the date.",
        "competition_date": body.competition_date.isoformat(),
        "ppm_enabled": False,
    }


@router.post("/disable")
async def disable_ppm(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Turn PPM off without setting a competition date (returns to fallback offseason)."""
    prof = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, "Profile not found.")
    prof.ppm_enabled = False
    prof.current_cycle_start_date = None
    prof.current_cycle_week = 1
    await db.flush()
    return {"ppm_enabled": False}


# ---------------------------------------------------------------------------
# Plan builder — integrates macro + meso + microcycle
# ---------------------------------------------------------------------------
def _build_cycle_plan(
    *,
    prof: UserProfile,
    metrics: dict,
    focus_muscles: list[str],
    mini_cut_active: bool,
) -> dict:
    """Assemble the full macrocycle plan from existing engine primitives.

    Structure returned:
        {
          "split": "<auto-selected split>",
          "focus_muscles": [...],
          "total_weeks": 14 or 16,
          "weeks": [
            {
              "week": 1..N,
              "ppm_sub_phase": "ppm_accumulation",
              "landmark_zone": "mev_to_mav",
              "rir": int, "fst7_mode": str,
              "per_muscle_sets": {muscle: {target_sets, is_focus, ...}},
              "macros": {protein_g, carbs_g, fat_g, target_calories,
                         carb_cycle: {...}},
              "day_rotation": [{"day_name", "muscles"}, ...],
            }, ...
          ]
        }
    """
    # ── Split selection ──
    # design_split() is the real strategic designer — it builds a custom
    # template from the athlete's gap profile, division archetype, recovery
    # windows, and equipment constraints. auto_select_split() was a shallow
    # template-picker and has been removed.
    from app.engines.engine2.split_designer import design_split

    days_per_week = prof.days_per_week or 5
    hqi_gaps: dict[str, float] = {}   # empty gaps → division archetype fallback
    design = design_split(
        hqi_gaps=hqi_gaps,
        division=prof.division,
        days_per_week=days_per_week,
    )
    split = "custom"
    day_rotation = design.get("template", [])
    split_reasoning = design.get("reasoning", "")

    # ── Volume landmarks scaled to athlete (training_status aware) ──
    landmarks = get_all_landmarks(
        training_years=prof.training_experience_years,
        training_status=prof.training_status,
    )

    # ── Macro scaffolding ──
    # TDEE uses compute_tdee with academic Cunningham (already switched).
    lbm_kg = metrics["lbm_kg"]
    body_weight_kg = metrics["body_weight_kg"] or (lbm_kg / 0.85)
    age = int(prof.age or 30)
    # PAL = 1.725 for active bodybuilders is a reasonable default.
    tdee = compute_tdee(
        weight_kg=body_weight_kg,
        height_cm=prof.height_cm,
        age=age,
        sex=prof.sex,
        activity_multiplier=1.725,
        lean_mass_kg=lbm_kg,
    )

    total_weeks = 16 if mini_cut_active else 14
    weeks_out: list[dict] = []
    for w in range(1, total_weeks + 1):
        sub_phase = ppm_phase_for_week(w, mini_cut_active=mini_cut_active)
        cycle_plan = compute_cycle_mesocycle(w, focus_muscles, landmarks)

        # Macros for this week (compute_macros aliases ppm_* to base phases
        # and returns a carb_cycle block).
        macros = compute_macros(
            tdee=tdee,
            phase=sub_phase,
            weight_kg=body_weight_kg,
            sex=prof.sex,
            lean_mass_kg=lbm_kg,
            body_fat_pct=metrics["bf_pct"],
        )

        # Surface the first muscle's landmark zone for the week-level header.
        sample_muscle = next(iter(cycle_plan.values()), {})
        landmark_zone = sample_muscle.get("landmark", "mev")
        rir = sample_muscle.get("rir", 2)
        fst7_mode = sample_muscle.get("fst7_mode", "none")

        weeks_out.append({
            "week": w,
            "ppm_sub_phase": sub_phase,
            "landmark_zone": landmark_zone,
            "rir": rir,
            "fst7_mode": fst7_mode,
            "per_muscle_sets": cycle_plan,
            "macros": macros,
            "day_rotation": day_rotation,
        })

    return {
        "split": split,
        "split_reasoning": split_reasoning,
        "focus_muscles": focus_muscles,
        "total_weeks": total_weeks,
        "weeks": weeks_out,
    }


def _round_delta(new_val, old_val):
    if new_val is None or old_val is None:
        return None
    try:
        return round(float(new_val) - float(old_val), 3)
    except (TypeError, ValueError):
        return None
