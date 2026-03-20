"""
Diagnostic Service — orchestrates Engine 1 modules with DB data.

Key changes from v1:
- Replaced HQI with Muscle Gaps (raw cm gap analysis)
- Division-specific PDS weights
- Multi-method body fat with confidence interval
- Response profiling from PDS history
- Annual phase calendar
- Enhanced symmetry details in PDS
- Cross-engine phase recommendation (Engine 1 → Engine 3)
"""
from datetime import date

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import TapeMeasurement, SkinfoldMeasurement, BodyWeightLog
from app.models.diagnostic import LCSALog, PDSLog, HQILog
from app.models.training import DivisionVector
from app.constants.divisions import DIVISION_VECTORS
from app.constants.division_classes import estimate_class

from app.engines.engine1.lcsa import compute_all_lcsa, compute_total_lcsa
from app.engines.engine1.muscle_gaps import (
    compute_total_gap, compute_avg_pct_of_ideal,
    rank_sites_by_gap,
)
from app.engines.engine1.volumetric_ghost import run_ghost_pipeline
from app.engines.engine1.aesthetic_vector import (
    compute_proportion_vector,
    compute_delta_vector,
    compute_priority_scores,
    cosine_similarity,
)
from app.engines.engine1.pds import (
    compute_pds,
    compute_muscle_mass_score,
    compute_conditioning_score,
    compute_symmetry_score,
    compute_symmetry_details,
    get_tier,
    get_division_weights,
)
from app.engines.engine1.trajectory import predict_trajectory
from app.engines.engine1.feasibility import compute_feasibility
from app.engines.engine1.body_fat import (
    jackson_pollock_7, categorize_body_fat, lean_mass_kg, navy_body_fat,
    lean_girth, compute_bf_composite,
)
from app.engines.engine1.prep_timeline import (
    prep_phase_for_date, weeks_out, phase_description, generate_annual_calendar,
)


TAPE_SITES = [
    "neck", "shoulders", "chest", "left_bicep", "right_bicep",
    "left_forearm", "right_forearm", "waist", "hips",
    "left_thigh", "right_thigh", "left_calf", "right_calf",
    "chest_relaxed", "chest_lat_spread", "back_width",
    "left_proximal_thigh", "right_proximal_thigh",
    "left_distal_thigh", "right_distal_thigh",
]

# Map bilateral tape columns to unified site names for gap/vector comparison
SITE_AVERAGE_MAP = {
    "neck": ["neck"],
    "shoulders": ["shoulders"],
    "chest": ["chest"],
    "bicep": ["left_bicep", "right_bicep"],
    "forearm": ["left_forearm", "right_forearm"],
    "waist": ["waist"],
    "hips": ["hips"],
    "thigh": ["left_thigh", "right_thigh"],
    "calf": ["left_calf", "right_calf"],
    # back_width is a single linear measurement (no bilateral averaging needed)
    "back_width": ["back_width"],
}

# Map averaged site name → skinfold column name for site-specific lean girth
_SITE_SKINFOLD_MAP = {
    "chest": "chest",
    "bicep": "bicep",
    "thigh": "thigh",
    "calf": "calf",
    "waist": "abdominal",
    "hips": "suprailiac",
    # Back width: use lower_back skinfold when available (best proxy for back subcutaneous fat)
    "back_width": "lower_back",
}


def _tape_to_dict(tape: TapeMeasurement) -> dict[str, float]:
    """Extract tape measurement values as dict."""
    result = {}
    for site in TAPE_SITES:
        val = getattr(tape, site, None)
        if val is not None:
            result[site] = val
    return result


def _average_sites(tape_dict: dict[str, float]) -> dict[str, float]:
    """Average bilateral sites for vector comparison."""
    averaged = {}
    for site, columns in SITE_AVERAGE_MAP.items():
        vals = [tape_dict[c] for c in columns if c in tape_dict]
        if vals:
            averaged[site] = sum(vals) / len(vals)
    return averaged


def _lean_adjust_measurements(
    averaged: dict[str, float],
    body_fat_pct: float,
    skinfold_data: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Strip fat from tape measurements before proportion/gap comparison.

    Two strategies (site-specific preferred when available):
    1. Lean girth formula (per-site skinfold): C_lean = C_total - pi * S_mm / 10
    2. Global fallback (overall BF%): lean_circ = raw * sqrt(1 - bf_fraction)
    """
    import math
    bf_fraction = max(0.0, min(body_fat_pct / 100.0, 0.50))
    global_factor = math.sqrt(1.0 - bf_fraction)

    result: dict[str, float] = {}
    for site, circ in averaged.items():
        sf_col = _SITE_SKINFOLD_MAP.get(site)
        if sf_col and skinfold_data and sf_col in skinfold_data:
            result[site] = lean_girth(circ, skinfold_data[sf_col])
        else:
            result[site] = round(circ * global_factor, 2)
    return result


async def get_latest_tape(db: AsyncSession, user_id) -> TapeMeasurement | None:
    result = await db.execute(
        select(TapeMeasurement)
        .where(TapeMeasurement.user_id == user_id)
        .order_by(desc(TapeMeasurement.recorded_date), desc(TapeMeasurement.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_skinfold(db: AsyncSession, user_id) -> SkinfoldMeasurement | None:
    result = await db.execute(
        select(SkinfoldMeasurement)
        .where(SkinfoldMeasurement.user_id == user_id)
        .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_weight(db: AsyncSession, user_id) -> BodyWeightLog | None:
    result = await db.execute(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == user_id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _recommend_phase(muscle_gaps: dict, pds_score: float, body_fat_pct: float | None, sex: str, profile_prefs: dict | None = None) -> dict:
    """
    Cross-engine feedback: Engine 1 → Engine 3 phase recommendation.
    Based on current physique state, suggest the optimal training phase.
    """
    avg_pct = compute_avg_pct_of_ideal(muscle_gaps)
    bf = body_fat_pct or 15.0

    if sex == "male":
        lean_threshold = 10.0
        fat_threshold = 18.0
    else:
        lean_threshold = 16.0
        fat_threshold = 25.0

    if profile_prefs and profile_prefs.get("cut_threshold_bf_pct") is not None:
        fat_threshold = float(profile_prefs["cut_threshold_bf_pct"])

    if avg_pct < 75 and bf < fat_threshold:
        return {
            "recommended_phase": "bulk",
            "reason": f"Muscle development at {avg_pct}% of ideal — prioritize building mass.",
            "confidence": "high",
        }
    elif avg_pct < 85 and bf < fat_threshold:
        return {
            "recommended_phase": "lean_bulk",
            "reason": f"Good foundation ({avg_pct}% of ideal) — controlled surplus to continue building.",
            "confidence": "medium",
        }
    elif bf > fat_threshold:
        return {
            "recommended_phase": "cut",
            "reason": f"Body fat at {bf}% — cut to reveal existing muscle before building more.",
            "confidence": "high",
        }
    elif bf <= lean_threshold and avg_pct >= 85:
        return {
            "recommended_phase": "maintain",
            "reason": f"Near ideal ({avg_pct}%) and lean ({bf}%) — maintain or prep for competition.",
            "confidence": "medium",
        }
    else:
        return {
            "recommended_phase": "lean_bulk",
            "reason": "Balanced state — controlled surplus for continued development.",
            "confidence": "low",
        }


async def run_full_diagnostic(db: AsyncSession, user: User) -> dict:
    """
    Run complete Engine 1 diagnostic pipeline.
    Returns dict with all computed values.
    """
    # Load profile
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise ValueError("User profile not found")

    # Load measurements
    tape = await get_latest_tape(db, user.id)
    if not tape:
        raise ValueError("No tape measurements found")

    skinfold = await get_latest_skinfold(db, user.id)
    body_fat_pct = skinfold.body_fat_pct if skinfold else None
    bf_source = None

    # Build skinfold and tape dicts for composite BF estimation
    sf_data: dict[str, float] | None = None
    tape_dict = _tape_to_dict(tape)

    if skinfold:
        sf_data = {}
        for col in ("chest", "tricep", "subscapular", "abdominal",
                     "suprailiac", "thigh", "bicep", "lower_back", "calf",
                     "midaxillary"):
            val = getattr(skinfold, col, None)
            if val is not None:
                sf_data[col] = val

    # Load Body Weight globally since it's used multiple places
    bw_result = await get_latest_weight(db, user.id)
    body_weight = bw_result.weight_kg if bw_result else None

    # Multi-method body fat estimation with confidence interval
    bf_composite = None
    if profile.manual_body_fat_pct is not None:
        body_fat_pct = profile.manual_body_fat_pct
        bf_source = "manual_override"
        bf_composite = {
            "primary_estimate": body_fat_pct,
            "confidence_range": (body_fat_pct, body_fat_pct),
            "spread": 0.0,
            "methods_used": ["Manual Override"],
            "individual_estimates": {"Manual Override": body_fat_pct},
            "confidence_level": "high",
        }
    elif sf_data or (tape.waist and tape.neck):
        body_weight_lbs = body_weight * 2.20462 if body_weight else None

        tape_data_for_bf = {
            "waist_cm": tape.waist,
            "neck_cm": tape.neck,
            "hips_cm": tape.hips,
        }

        bf_composite = compute_bf_composite(
            skinfold_data=sf_data or {},
            tape_data=tape_data_for_bf,
            age=profile.age or 30,
            sex=profile.sex,
            height_cm=profile.height_cm,
            body_weight_kg=body_weight,
        )

        if bf_composite and bf_composite.get("primary_estimate"):
            body_fat_pct = bf_composite["primary_estimate"]
            bf_source = "composite"

    # Fallback: single-method BF estimation
    if body_fat_pct is None and skinfold and profile.age:
        try:
            body_fat_pct = jackson_pollock_7(
                chest=skinfold.chest or 0,
                midaxillary=skinfold.midaxillary or 0,
                tricep=skinfold.tricep or 0,
                subscapular=skinfold.subscapular or 0,
                abdominal=skinfold.abdominal or 0,
                suprailiac=skinfold.suprailiac or 0,
                thigh=skinfold.thigh or 0,
                age=profile.age,
                sex=profile.sex,
            )
            if skinfold:
                skinfold.body_fat_pct = body_fat_pct
            bf_source = "jackson_pollock_7"
        except (ValueError, ZeroDivisionError):
            body_fat_pct = None

    if body_fat_pct is None and tape.waist and tape.neck and profile.height_cm:
        try:
            body_fat_pct = navy_body_fat(
                waist_cm=tape.waist,
                neck_cm=tape.neck,
                height_cm=profile.height_cm,
                sex=profile.sex,
                hips_cm=tape.hips,
            )
            bf_source = "navy_circumference"
        except Exception:
            pass

    averaged = _average_sites(tape_dict)
    division_vector = DIVISION_VECTORS.get(profile.division, DIVISION_VECTORS["mens_open"])

    # Use chest_relaxed for chest gaps when available
    if tape.chest_relaxed:
        averaged["chest"] = tape.chest_relaxed

    # Lean-adjust circumferences
    lean_averaged = _lean_adjust_measurements(averaged, body_fat_pct or 15.0, sf_data)

    # LCSA
    lcsa_values = compute_all_lcsa(tape_dict, body_fat_pct)
    total_lcsa = compute_total_lcsa(lcsa_values)

    # Volumetric Ghost Model — 3D biomechanical proportion analysis
    ghost_result = run_ghost_pipeline(
        height_cm=profile.height_cm,
        division=profile.division,
        lean_measurements=lean_averaged,
        sex=profile.sex,
    )
    muscle_gaps = ghost_result["site_scores"]
    ideal_circs = ghost_result["ideal_circumferences"]
    total_gap = compute_total_gap(muscle_gaps)
    avg_pct = compute_avg_pct_of_ideal(muscle_gaps, division=profile.division)

    # Class estimation
    class_estimate = estimate_class(
        height_cm=profile.height_cm,
        division=profile.division,
        body_weight_kg=body_weight,
    )

    # Aesthetic Vector
    proportion_vector = compute_proportion_vector(lean_averaged, profile.height_cm)
    delta_vector = compute_delta_vector(proportion_vector, division_vector)
    priority_scores = compute_priority_scores(delta_vector, division=profile.division)
    similarity = cosine_similarity(proportion_vector, division_vector)

    # Aesthetic score
    import math as _math
    common = [s for s in division_vector if s in proportion_vector and s not in ("shoulder_to_waist", "v_taper")]
    if common:
        squared_errors = [(proportion_vector[s] - division_vector[s]) ** 2 for s in common]
        rmse = _math.sqrt(sum(squared_errors) / len(squared_errors))
        rmse_score = max(0.0, 1.0 - rmse / 0.05)
        aesthetic_score = round((0.5 * similarity + 0.5 * rmse_score) * 100, 1)
    else:
        aesthetic_score = similarity * 100

    mass_score = compute_muscle_mass_score(total_lcsa, profile.height_cm, profile.sex)
    cond_score = compute_conditioning_score(body_fat_pct, profile.sex)
    sym_score = compute_symmetry_score(tape_dict)
    sym_details = compute_symmetry_details(tape_dict)

    # Division-specific PDS
    pds_score = compute_pds(aesthetic_score, mass_score, cond_score, sym_score, division=profile.division)
    tier = get_tier(pds_score)
    pds_weights = get_division_weights(profile.division)

    # Weight cap (from Ghost pipeline — IFBB table lookup)
    weight_cap = {
        "weight_cap_kg": ghost_result["weight_cap_kg"],
        "target_lbm_kg": ghost_result["target_lbm_kg"],
        "stage_weight_kg": ghost_result["weight_cap_kg"],
        "ghost_mass_kg": ghost_result["ghost_mass_kg"],
        "allometric_multiplier": ghost_result["allometric_multiplier"],
    }

    # Prep timeline + annual calendar
    comp_date = getattr(profile, "competition_date", None)
    current_phase = prep_phase_for_date(comp_date)
    phase_info = phase_description(current_phase)
    weeks_remaining = weeks_out(comp_date)
    annual_calendar = generate_annual_calendar(comp_date) if comp_date else None

    # Body fat details
    body_fat_info = None
    if body_fat_pct is not None:
        body_fat_info = {
            "body_fat_pct": body_fat_pct,
            "category": categorize_body_fat(body_fat_pct, profile.sex),
            "lean_mass_kg": lean_mass_kg(body_weight, body_fat_pct) if body_weight else None,
            "source": bf_source or "skinfold",
        }
        if bf_composite:
            body_fat_info["confidence_range"] = bf_composite.get("confidence_range")
            body_fat_info["confidence_level"] = bf_composite.get("confidence_level")
            body_fat_info["methods_used"] = bf_composite.get("methods_used")
            body_fat_info["individual_estimates"] = bf_composite.get("individual_estimates")

    # Phase recommendation (cross-engine: E1 → E3)
    phase_recommendation = _recommend_phase(muscle_gaps, pds_score, body_fat_pct, profile.sex, profile.preferences)

    # Response profiling from PDS history
    response_profile = None
    try:
        from app.engines.engine1.trajectory import compute_response_ratio
        pds_history = await get_pds_history(db, user.id)
        if len(pds_history) >= 3:
            response_profile = compute_response_ratio(pds_history)
    except Exception:
        pass

    # Trajectory (next 52 weeks) — personalized if response data available
    ceiling_pds = min(95.0, pds_score + 30)
    if response_profile and response_profile.get("response_ratio"):
        from app.engines.engine1.trajectory import personalized_trajectory
        trajectory = personalized_trajectory(
            pds_score, ceiling_pds, 52,
            response_profile["response_ratio"],
            profile.training_experience_years,
        )
    else:
        trajectory = predict_trajectory(pds_score, ceiling_pds, 52, profile.training_experience_years)

    today = date.today()

    # Persist LCSA
    lcsa_log = LCSALog(
        user_id=user.id,
        recorded_date=today,
        site_values=lcsa_values,
        total_lcsa=total_lcsa,
    )
    db.add(lcsa_log)

    # Persist Muscle Gaps (stored in HQILog for backward compat — data format changed)
    hqi_log = HQILog(
        user_id=user.id,
        recorded_date=today,
        site_scores=muscle_gaps,
        overall_hqi=avg_pct,
    )
    db.add(hqi_log)

    # Persist PDS
    component_scores = {
        "aesthetic": aesthetic_score,
        "muscle_mass": mass_score,
        "conditioning": cond_score,
        "symmetry": sym_score,
    }
    pds_log = PDSLog(
        user_id=user.id,
        recorded_date=today,
        pds_score=pds_score,
        component_scores=component_scores,
        tier=tier,
    )
    db.add(pds_log)

    await db.flush()

    return {
        "lcsa": {"site_values": lcsa_values, "total": total_lcsa},
        "muscle_gaps": {
            "sites": muscle_gaps,
            "total_gap_cm": total_gap,
            "avg_pct_of_ideal": avg_pct,
            "ranked_gaps": rank_sites_by_gap(muscle_gaps),
        },
        "pds": {
            "score": pds_score,
            "tier": tier,
            "components": component_scores,
            "weights": pds_weights,
        },
        "symmetry": {
            "score": sym_score,
            "details": sym_details,
        },
        "aesthetic_vector": {
            "actual": proportion_vector,
            "delta": delta_vector,
            "priorities": priority_scores,
            "similarity": similarity,
        },
        "weight_cap": weight_cap,
        "trajectory": trajectory,
        "body_fat": body_fat_info,
        "prep_timeline": {
            "current_phase": current_phase,
            "weeks_out": weeks_remaining,
            "phase_info": phase_info,
            "annual_calendar": annual_calendar,
        },
        "phase_recommendation": phase_recommendation,
        "response_profile": response_profile,
        "advanced_measurements": _build_advanced_measurements(tape, lean_averaged),
        "class_estimate": class_estimate,
        "ghost_model": {
            "ghost_mass_kg": ghost_result["ghost_mass_kg"],
            "allometric_multiplier": ghost_result["allometric_multiplier"],
            "hanavan_volumes": ghost_result["hanavan_volumes"],
            "scaled_ghost": ghost_result["scaled_ghost"],
        },
    }


def _build_advanced_measurements(tape: TapeMeasurement, lean_averaged: dict[str, float]) -> dict | None:
    """
    Extract advanced measurement insights and compute scored metrics for
    back isolation, lat activation, and quad regionality.
    """
    result: dict = {}

    # --- Chest / Back Isolation ---
    chest_r = getattr(tape, "chest_relaxed", None)
    chest_ls = getattr(tape, "chest_lat_spread", None)
    if chest_r and chest_ls:
        delta = round(chest_ls - chest_r, 1)
        result["lat_spread_delta_cm"] = delta
        result["chest_relaxed_cm"] = round(chest_r, 1)
        result["chest_lat_spread_cm"] = round(chest_ls, 1)
        result["lean_chest_used_cm"] = lean_averaged.get("chest")
        # Lat activation %: how much of the relaxed chest circumference is lat-driven
        # Competitive target: 3–7% (tighter = weaker lat flare)
        lat_pct = round((delta / chest_r) * 100, 1) if chest_r > 0 else 0.0
        result["lat_activation_pct"] = lat_pct
        # Score 0–100: 7%+ = 100, 0% = 0
        result["lat_activation_score"] = round(min(100.0, (lat_pct / 7.0) * 100), 1)

    # --- Back Width (now flows into muscle_gaps via lean_averaged) ---
    back_w = getattr(tape, "back_width", None)
    if back_w:
        result["back_width_cm"] = round(back_w, 1)
        result["lean_back_width_cm"] = lean_averaged.get("back_width")

    # --- Quad Regionality (VMO / Teardrop development) ---
    prox_l = getattr(tape, "left_proximal_thigh", None)
    prox_r = getattr(tape, "right_proximal_thigh", None)
    dist_l = getattr(tape, "left_distal_thigh", None)
    dist_r = getattr(tape, "right_distal_thigh", None)

    proximal_cm = None
    distal_cm = None

    if prox_l or prox_r:
        vals = [v for v in (prox_l, prox_r) if v]
        proximal_cm = round(sum(vals) / len(vals), 1)
        result["proximal_thigh_cm"] = proximal_cm

    if dist_l or dist_r:
        vals = [v for v in (dist_l, dist_r) if v]
        distal_cm = round(sum(vals) / len(vals), 1)
        result["distal_thigh_cm"] = distal_cm

    if proximal_cm and distal_cm and proximal_cm > 0:
        # VMO ratio: distal / proximal — competitive target 0.76–0.82
        # Higher ratio = more VMO teardrop development relative to upper quad
        quad_ratio = round(distal_cm / proximal_cm, 3)
        result["quad_vmo_ratio"] = quad_ratio
        # Score 0–100: 0.80 ratio = 100, 0.60 = 0
        result["quad_regionality_score"] = round(
            min(100.0, max(0.0, (quad_ratio - 0.60) / (0.80 - 0.60) * 100)), 1
        )

    return result if result else None


async def get_pds_history(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(PDSLog)
        .where(PDSLog.user_id == user_id)
        .order_by(PDSLog.recorded_date)
    )
    logs = result.scalars().all()
    return [
        {
            "date": str(log.recorded_date),
            "pds_score": log.pds_score,
            "tier": log.tier,
            "components": log.component_scores,
        }
        for log in logs
    ]


async def get_lcsa_history(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(LCSALog)
        .where(LCSALog.user_id == user_id)
        .order_by(LCSALog.recorded_date)
    )
    logs = result.scalars().all()
    return [
        {
            "date": str(log.recorded_date),
            "site_values": log.site_values,
            "total": log.total_lcsa,
        }
        for log in logs
    ]
