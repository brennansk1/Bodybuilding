from __future__ import annotations

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
import logging
from datetime import date

logger = logging.getLogger(__name__)

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
    "chest_relaxed": ["chest_relaxed"],
    "chest_lat_spread": ["chest_lat_spread"],
    "bicep": ["left_bicep", "right_bicep"],
    "forearm": ["left_forearm", "right_forearm"],
    "waist": ["waist"],
    "hips": ["hips"],
    "thigh": ["left_thigh", "right_thigh"],
    "proximal_thigh": ["left_proximal_thigh", "right_proximal_thigh"],
    "distal_thigh": ["left_distal_thigh", "right_distal_thigh"],
    "calf": ["left_calf", "right_calf"],
    "back_width": ["back_width"],
}

# Map averaged site name → skinfold column name for site-specific lean girth
_SITE_SKINFOLD_MAP = {
    "chest": "chest",
    "chest_relaxed": "chest",
    "chest_lat_spread": "chest",
    "bicep": "bicep",
    "thigh": "thigh",
    "proximal_thigh": "thigh",
    "distal_thigh": "thigh",
    "calf": "calf",
    "waist": "abdominal",
    "hips": "suprailiac",
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
    sex: str = "male",
) -> dict[str, float]:
    """
    Strip fat from tape measurements before proportion/gap comparison.

    V2 unification (audit fix) — routes every site through
    `engine1.girth_projection.project_lean`, which enforces the same
    three-tier dispatch (ISAK skinfold → JP-derived → BF-linear floor) that
    the rest of the V2 engines use. Previously this function used an
    inline sqrt(1 - bf_fraction) global fallback that diverged from the
    V2 canonical path by ~3-10% per site. Now both surfaces agree.

    Sources per strategy:
      - ISAK manual / Heymsfield 1982 (primary skinfold path)
      - Jackson & Pollock 1978 (fallback from total BF%)
    """
    from app.engines.engine1.girth_projection import project_lean

    result: dict[str, float] = {}
    for site, circ in averaged.items():
        projection = project_lean(
            raw_cm=circ,
            site=site,
            skinfold_row=skinfold_data,  # project_lean handles both dict + ORM
            bf_pct=body_fat_pct,
            sex=sex,
        )
        result[site] = round(projection["lean_cm"], 2)
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


def _recommend_phase(
    muscle_gaps: dict,
    pds_score: float,
    body_fat_pct: float | None,
    sex: str,
    profile_prefs: dict | None = None,
    competition_date=None,
    weeks_out: int | None = None,
    body_weight_kg: float = 85.0,
) -> dict:
    """
    Cross-engine feedback: Engine 1 → Engine 3 phase recommendation.

    Considers competition date, LBM adequacy (muscle gaps), AND body fat.
    An athlete who is undermuscled should NOT be told to cut just because
    BF% is above a threshold — they need muscle mass first, then cut.

    Phase priority:
      1. If competition is <20 weeks out and BF is high → cut (no choice)
      2. If competition is ≤1 week out → peak_week
      3. If far out (>30 weeks) and undermuscled → bulk/lean_bulk regardless of BF
      4. If moderate BF (>fat_threshold) but >20 weeks out and undermuscled → lean_bulk
         (build muscle in a slight surplus; BF will come down during the cut phase later)
      5. If BF is very high (>25% male / >32% female) → always cut first (health)
      6. Standard logic for remaining cases
    """
    avg_pct = compute_avg_pct_of_ideal(muscle_gaps)
    bf = body_fat_pct or 15.0

    if sex == "male":
        lean_threshold = 10.0
        fat_threshold = 18.0
        health_threshold = 25.0  # above this, cut regardless
    else:
        lean_threshold = 16.0
        fat_threshold = 25.0
        health_threshold = 32.0

    if profile_prefs and profile_prefs.get("cut_threshold_bf_pct") is not None:
        fat_threshold = float(profile_prefs["cut_threshold_bf_pct"])

    # Calculate weeks out if competition date provided
    if weeks_out is None and competition_date:
        from datetime import date as date_type
        if isinstance(competition_date, str):
            try:
                competition_date = date_type.fromisoformat(competition_date)
            except ValueError:
                competition_date = None
        if competition_date:
            days = (competition_date - date_type.today()).days
            weeks_out = max(0, days // 7) if days > 0 else None

    # --- Priority 1: Very high BF (health risk) → always cut ---
    if bf > health_threshold:
        return {
            "recommended_phase": "cut",
            "reason": f"Body fat at {bf:.1f}% exceeds health threshold — cut to reduce metabolic risk.",
            "confidence": "high",
        }

    # --- Priority 2: Peak week (≤1 week out) ---
    if weeks_out is not None and weeks_out <= 1:
        return {
            "recommended_phase": "peak_week",
            "reason": f"{weeks_out} weeks to show — peak week protocol.",
            "confidence": "high",
        }

    # --- Priority 3: Competition scheduled — use smart prep planner ---
    if weeks_out is not None and competition_date is not None and body_fat_pct is not None:
        from app.engines.engine1.prep_timeline import (
            estimate_cut_duration, get_stage_bf_target, compute_smart_phase_plan,
        )
        from datetime import date as _date

        comp_d = competition_date
        if isinstance(comp_d, str):
            try:
                comp_d = _date.fromisoformat(comp_d)
            except ValueError:
                comp_d = None

        if comp_d:
            division_key = (profile_prefs or {}).get("division", "classic_physique")
            target_bf = get_stage_bf_target(division_key, sex)
            cut_est = estimate_cut_duration(bf, target_bf, body_weight_kg, sex)
            cut_needed = cut_est["weeks_needed"]

            # Build feasibility info to attach to the recommendation
            prep_info = {
                "cut_weeks_needed": cut_needed,
                "weeks_available": weeks_out,
                "target_stage_bf_pct": target_bf,
                "fat_to_lose_kg": cut_est["fat_kg_to_lose"],
                "projected_stage_weight_kg": cut_est["projected_stage_weight"],
                "feasible": weeks_out >= (cut_needed + 1),
            }

            if weeks_out <= 1:
                pass  # Handled by Priority 2 above

            elif bf <= target_bf + 1.5:
                # Already lean enough — maintain or light cut
                return {
                    "recommended_phase": "maintain" if bf <= target_bf + 0.5 else "cut",
                    "reason": f"Already at {bf:.1f}% BF (target {target_bf:.1f}%). "
                              f"{'Maintain conditioning.' if bf <= target_bf + 0.5 else 'Light deficit to dial in final conditioning.'}",
                    "confidence": "high",
                    "prep_plan": prep_info,
                }

            elif weeks_out <= cut_needed + 1:
                # Tight timeline — start cutting NOW, get as close as possible
                if weeks_out < cut_needed - 2:
                    from app.engines.engine1.prep_timeline import _simulate_cut_to_deadline
                    sim = _simulate_cut_to_deadline(bf, target_bf, body_weight_kg, max(0, weeks_out - 1))
                    prep_info["projected_stage_bf_pct"] = sim["projected_bf_pct"]
                    prep_info["ideal_conditioning"] = sim["reached_target"]
                return {
                    "recommended_phase": "cut",
                    "reason": (
                        f"{weeks_out} weeks to show. Ideal cut is ~{cut_needed} weeks "
                        f"({bf:.1f}% → {target_bf:.1f}% BF). "
                        f"{'Start cutting immediately — ' if weeks_out <= cut_needed else 'Begin cut now — '}"
                        f"maximizing conditioning within the available timeline."
                    ),
                    "confidence": "high",
                    "prep_plan": prep_info,
                }

            else:
                # Extra time — lean bulk first, then cut
                bulk_weeks = weeks_out - cut_needed - 1  # -1 for peak week

                # BF ceiling for productive bulking: above ~16% (male) / ~25% (female)
                # nutrient partitioning is poor — surplus goes to fat, not muscle.
                # No Olympia-level coach would bulk an athlete above this threshold.
                bulk_bf_ceiling = 16.0 if sex == "male" else 25.0
                bf_too_high = bf > bulk_bf_ceiling

                if bf_too_high:
                    # BF is too high for productive bulking — cut immediately.
                    # The extended timeline allows a gentler, more sustainable deficit.
                    return {
                        "recommended_phase": "cut",
                        "reason": (
                            f"Body fat at {bf:.1f}% exceeds the {bulk_bf_ceiling:.0f}% ceiling "
                            f"for productive bulking (poor nutrient partitioning). "
                            f"Cut immediately — the {weeks_out}-week timeline allows a gentle "
                            f"deficit with diet breaks for muscle preservation."
                        ),
                        "confidence": "high",
                        "prep_plan": prep_info,
                    }
                elif avg_pct < 80 and not bf_too_high:
                    phase = "bulk" if avg_pct < 70 and bulk_weeks > 8 else "lean_bulk"
                    return {
                        "recommended_phase": phase,
                        "reason": (
                            f"Muscle at {avg_pct:.0f}% of ideal with {weeks_out} weeks to show. "
                            f"{phase.replace('_', ' ').title()} for {bulk_weeks} weeks, "
                            f"then {cut_needed}-week cut to reach {target_bf:.1f}% BF."
                        ),
                        "confidence": "high",
                        "prep_plan": prep_info,
                    }
                else:
                    return {
                        "recommended_phase": "lean_bulk",
                        "reason": (
                            f"Good position: {bf:.1f}% BF, {weeks_out} weeks to show. "
                            f"Lean bulk for {bulk_weeks} weeks to maximize stage size, "
                            f"then {cut_needed}-week cut to reach {target_bf:.1f}% BF."
                        ),
                        "confidence": "high",
                        "prep_plan": prep_info,
                    }

    # --- No competition date: use standard logic with muscle adequacy ---
    if avg_pct < 75 and bf < health_threshold:
        return {
            "recommended_phase": "bulk",
            "reason": f"Muscle development at {avg_pct:.0f}% of ideal — prioritize building mass.",
            "confidence": "high",
        }
    elif avg_pct < 85 and bf < fat_threshold:
        return {
            "recommended_phase": "lean_bulk",
            "reason": f"Good foundation ({avg_pct:.0f}% of ideal) — controlled surplus to continue building.",
            "confidence": "medium",
        }
    elif bf > fat_threshold:
        # BF is high but check muscle adequacy — undermuscled athletes
        # benefit from lean bulking even at moderate BF levels
        if avg_pct < 80:
            return {
                "recommended_phase": "lean_bulk",
                "reason": (
                    f"BF at {bf:.1f}% is elevated but muscle development is only {avg_pct:.0f}% of ideal — "
                    f"lean bulk to build foundation before cutting."
                ),
                "confidence": "medium",
            }
        return {
            "recommended_phase": "cut",
            "reason": f"Body fat at {bf:.1f}% with good muscle base ({avg_pct:.0f}%) — cut to reveal existing muscle.",
            "confidence": "high",
        }
    elif bf <= lean_threshold and avg_pct >= 85:
        return {
            "recommended_phase": "maintain",
            "reason": f"Near ideal ({avg_pct:.0f}%) and lean ({bf:.1f}%) — maintain or prep for competition.",
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
        except (ValueError, ZeroDivisionError) as e:
            logger.warning("Navy BF in diagnostic failed: %s", e)

    averaged = _average_sites(tape_dict)
    division_vector = DIVISION_VECTORS.get(profile.division, DIVISION_VECTORS["mens_open"])

    # Use chest_relaxed for chest gaps when available
    if tape.chest_relaxed:
        averaged["chest"] = tape.chest_relaxed

    # Lean-adjust circumferences
    lean_averaged = _lean_adjust_measurements(
        averaged, body_fat_pct or 15.0, sf_data, sex=profile.sex or "male",
    )

    # LCSA — fault-tolerant
    lcsa_values: dict = {}
    total_lcsa: float = 0.0
    try:
        lcsa_values = compute_all_lcsa(tape_dict, body_fat_pct)
        total_lcsa = compute_total_lcsa(lcsa_values)
    except Exception as _e:
        logger.warning("LCSA computation failed: %s", _e)

    # Volumetric Ghost Model — 3D biomechanical proportion analysis (fault-tolerant)
    ghost_result: dict = {}
    muscle_gaps: dict = {}
    total_gap: float = 0.0
    avg_pct: float = 0.0
    weight_cap: dict | None = None
    ghost_model_data: dict | None = None
    try:
        ghost_result = run_ghost_pipeline(
            height_cm=profile.height_cm,
            division=profile.division,
            lean_measurements=lean_averaged,
            sex=profile.sex,
        )
        muscle_gaps = ghost_result["site_scores"]
        total_gap = compute_total_gap(muscle_gaps)
        avg_pct = compute_avg_pct_of_ideal(muscle_gaps, division=profile.division)
        weight_cap = {
            "weight_cap_kg": ghost_result["weight_cap_kg"],
            "target_lbm_kg": ghost_result["target_lbm_kg"],
            "stage_weight_kg": ghost_result["weight_cap_kg"],
            "ghost_mass_kg": ghost_result["ghost_mass_kg"],
            "allometric_multiplier": ghost_result["allometric_multiplier"],
        }
        ghost_model_data = {
            "ghost_mass_kg": ghost_result["ghost_mass_kg"],
            "allometric_multiplier": ghost_result["allometric_multiplier"],
            "hanavan_volumes": ghost_result["hanavan_volumes"],
            "scaled_ghost": ghost_result["scaled_ghost"],
        }
    except Exception as _e:
        logger.warning("Ghost pipeline failed: %s", _e)

    # Class estimation — fault-tolerant
    class_estimate = None
    try:
        class_estimate = estimate_class(
            height_cm=profile.height_cm,
            division=profile.division,
            body_weight_kg=body_weight,
        )
    except Exception as _e:
        logger.warning("Class estimation failed: %s", _e)

    # Aesthetic Vector — fault-tolerant
    proportion_vector: dict = {}
    delta_vector: dict = {}
    priority_scores: dict = {}
    similarity: float = 0.0
    aesthetic_score: float = 50.0
    try:
        proportion_vector = compute_proportion_vector(lean_averaged, profile.height_cm)
        delta_vector = compute_delta_vector(proportion_vector, division_vector)
        priority_scores = compute_priority_scores(delta_vector, division=profile.division)
        similarity = cosine_similarity(proportion_vector, division_vector)

        import math as _math
        common = [s for s in division_vector if s in proportion_vector and s not in ("shoulder_to_waist", "v_taper")]
        if common:
            squared_errors = [(proportion_vector[s] - division_vector[s]) ** 2 for s in common]
            rmse = _math.sqrt(sum(squared_errors) / len(squared_errors))
            rmse_score = max(0.0, 1.0 - rmse / 0.05)
            aesthetic_score = round((0.5 * similarity + 0.5 * rmse_score) * 100, 1)
        else:
            aesthetic_score = similarity * 100
    except Exception as _e:
        logger.warning("Aesthetic vector computation failed: %s", _e)

    # Prep timeline + annual calendar (computed early so phase feeds into conditioning score)
    comp_date = getattr(profile, "competition_date", None)
    current_phase = prep_phase_for_date(comp_date)
    phase_info = phase_description(current_phase)
    weeks_remaining = weeks_out(comp_date)
    annual_calendar = generate_annual_calendar(comp_date) if comp_date else None

    # PDS components — fault-tolerant
    mass_score: float = 0.0
    cond_score: float = 50.0
    sym_score: float = 100.0
    sym_details: list = []
    pds_score: float = 0.0
    tier: str = "novice"
    pds_weights: dict = {}
    try:
        mass_score = compute_muscle_mass_score(total_lcsa, profile.height_cm, profile.sex)
        cond_score = compute_conditioning_score(body_fat_pct, profile.sex, phase=current_phase or "offseason")
        sym_score = compute_symmetry_score(tape_dict)
        sym_details = compute_symmetry_details(tape_dict)
        pds_score = compute_pds(aesthetic_score, mass_score, cond_score, sym_score, division=profile.division)
        tier = get_tier(pds_score)
        pds_weights = get_division_weights(profile.division)
    except Exception as _e:
        logger.warning("PDS computation failed: %s", _e)

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
    phase_recommendation = _recommend_phase(muscle_gaps, pds_score, body_fat_pct, profile.sex, profile.preferences, competition_date=profile.competition_date)

    # Response profiling from PDS history
    response_profile = None
    try:
        from app.engines.engine1.trajectory import compute_response_ratio
        pds_history = await get_pds_history(db, user.id)
        if len(pds_history) >= 3:
            response_profile = compute_response_ratio(pds_history)
    except Exception as e:
        logger.warning("Response profile computation failed: %s", e)

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
    component_scores = {
        "aesthetic": aesthetic_score,
        "muscle_mass": mass_score,
        "conditioning": cond_score,
        "symmetry": sym_score,
    }

    # Persist computed data — fault-tolerant so a DB error doesn't mask results
    try:
        if lcsa_values:
            db.add(LCSALog(
                user_id=user.id,
                recorded_date=today,
                site_values=lcsa_values,
                total_lcsa=total_lcsa,
            ))
        if muscle_gaps:
            db.add(HQILog(
                user_id=user.id,
                recorded_date=today,
                site_scores=muscle_gaps,
                overall_hqi=avg_pct,
            ))
        db.add(PDSLog(
            user_id=user.id,
            recorded_date=today,
            pds_score=pds_score,
            component_scores=component_scores,
            tier=tier,
        ))
        await db.flush()
    except Exception as _e:
        logger.warning("Failed to persist diagnostic logs: %s", _e)

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
        "ghost_model": ghost_model_data,
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
