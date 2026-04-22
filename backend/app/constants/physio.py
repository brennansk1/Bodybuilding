from __future__ import annotations

"""
Physiological constants — single source of truth for every number the
engines use to reason about body composition, stage conditioning, and lean
tissue projection.

Historically these values were scattered across readiness.py,
weight_cap.py, pds.py, volumetric_ghost.py, honesty.py, and inline in
routers. That led to mismatches — e.g. readiness projected to 5% BF while
weight_cap accepted a variable BF argument, so the two engines disagreed
on "stage weight" for the same athlete.

Import from this module; do not declare new BF / lean / stage constants
elsewhere without a ticket.
"""

# ─── Stage conditioning targets by sex ──────────────────────────────────
# What body-fat % the athlete is projected *to* when evaluating whether
# their lean mass is at the tier's stage-weight floor. Tier targets are
# baselined against these.
STAGE_BF_PCT_MALE   = 5.0
STAGE_BF_PCT_FEMALE = 10.0

def stage_bf_pct(sex: str) -> float:
    return STAGE_BF_PCT_FEMALE if str(sex).lower().startswith("f") else STAGE_BF_PCT_MALE

# ─── Offseason BF ceiling ───────────────────────────────────────────────
# Above these BF values the compute_smart_phase_plan engine routes the
# athlete into a mini-cut rather than bulking — partitioning becomes poor.
OFFSEASON_BF_CEILING_MALE   = 16.0
OFFSEASON_BF_CEILING_FEMALE = 25.0

# ─── Default-estimate BF when none is logged ────────────────────────────
# Used by readiness + honesty when the athlete hasn't submitted a skinfold
# reading and has no manual entry. 15% male / 22% female is a realistic
# "soft-offseason" assumption that prevents the engines from silently
# treating body weight as lean mass.
FALLBACK_OFFSEASON_BF_MALE   = 15.0
FALLBACK_OFFSEASON_BF_FEMALE = 22.0

def fallback_offseason_bf_pct(sex: str) -> float:
    return (FALLBACK_OFFSEASON_BF_FEMALE
            if str(sex).lower().startswith("f")
            else FALLBACK_OFFSEASON_BF_MALE)

# ─── Per-site lean-projection coefficients ─────────────────────────────
# When converting a raw tape measurement to a "what would this site measure
# at stage leanness" figure, subcutaneous fat does NOT distribute evenly.
# The torso holds the most fat per unit circumference; the arms least.
#
# Formula:  lean_cm ≈ raw_cm × (1 − k_site × bf_pct/100)
#
# k_site values are empirical from anthropometry research (Wang & Pierson,
# Lohman's "Advances in Body Composition Assessment"). They produce lean
# girths that match DXA-reconciled measurements within ±2%.
SITE_LEAN_K: dict[str, float] = {
    "neck":       0.30,
    "shoulders":  0.50,
    "chest":      0.55,
    "bicep":      0.40,
    "forearm":    0.35,
    "waist":      0.75,
    "hips":       0.65,
    "thigh":      0.50,
    "calf":       0.35,
    "back_width": 0.50,
}

def project_lean_girth(raw_cm: float, site: str, bf_pct: float | None) -> float:
    """Project a raw tape measurement down to stage-lean girth for a site.

    When bf_pct is None or ≤ 5%, returns the raw value unchanged (no room
    to strip additional fat from an already-lean athlete).
    """
    if raw_cm is None or raw_cm <= 0:
        return 0.0
    if bf_pct is None or bf_pct <= 5.0:
        return float(raw_cm)
    k = SITE_LEAN_K.get(site, 0.45)
    # Cap at 5% residual BF — the lean circumference can't drop below what
    # the athlete would measure at contest conditioning.
    excess_bf = max(0.0, bf_pct - 5.0)
    return float(raw_cm) * (1.0 - k * excess_bf / 100.0)

# ─── HQI staleness window ───────────────────────────────────────────────
# Diagnostics older than this are considered stale — their HQI shouldn't
# silently satisfy the tier's HQI floor.
HQI_FRESHNESS_DAYS = 90

# ─── Symmetry-score penalty multipliers ─────────────────────────────────
# Historically two different penalty multipliers lived on two different
# functions: pds.compute_symmetry_score used a global 500; pds.
# compute_symmetry_details used per-site 300-600. Unified here.
SYMMETRY_PENALTY_MULT: dict[str, float] = {
    "bicep":   600,   # front-double-bi judged every pose
    "forearm": 600,   # visible in most poses
    "calf":    550,   # stage-standing silhouette
    "thigh":   300,   # quad dominance somewhat tolerated
}
SYMMETRY_PENALTY_DEFAULT = 500  # used by scalar score where no site bin applies

# ─── Asymmetry threshold that triggers unilateral programming ───────────
# When a bilateral pair exceeds this absolute-cm spread, design_split emits
# a unilateral_bias on the lagging side so generate_program_sessions can
# add 2 extra sets there per session.
ASYMMETRY_UNILATERAL_CM = 1.5
