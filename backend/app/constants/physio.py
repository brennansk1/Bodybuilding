from __future__ import annotations

"""
Physiological constants — single source of truth for every number the
engines use to reason about body composition, stage conditioning, and
lean-tissue projection.

Every constant carries a `provenance` string (citation). When a number is
a prior rather than a measured value (k-coefficients, penalty multipliers),
the source field says so — that way future recalibration sprints against a
validation corpus can identify which numbers are load-bearing priors.

Do not declare new BF / lean / stage constants elsewhere without a ticket.
"""

from app.constants.types import ValueWithUncertainty


# ---------------------------------------------------------------------------
# Stage conditioning targets per division
# ---------------------------------------------------------------------------
# What body-fat % the athlete is projected *to* when evaluating whether
# their lean mass is at the tier's stage-weight floor. Division-specific
# because Bikini (≈12% F) and Men's Physique (≈6.5% M) are not judged at
# the same absolute leanness.
#
# Sources:
#   - Helms, Aragon & Fitschen 2014 (J Int Soc Sports Nutr 11:20)
#   - Iraki, Fitschen, Espinar & Helms 2019 (Sports 7:154)
#   - Hulmi et al. 2017 — women's physique / figure prep
#   - Rossow et al. 2013 — 12-month case study
#   - Chappell et al. 2018 (J Int Soc Sports Nutr 15:4) — female divisions
STAGE_BF_PCT_BY_DIVISION: dict[str, ValueWithUncertainty] = {
    "mens_open":        ValueWithUncertainty(4.0, 1.0, "Helms 2014 / Rossow 2013", "3–5%"),
    "classic_physique": ValueWithUncertainty(5.0, 1.0, "Helms 2014 / Hulmi 2017", "4–6%"),
    "mens_physique":    ValueWithUncertainty(6.5, 1.5, "Helms 2014", "5–8%"),
    "womens_bikini":    ValueWithUncertainty(12.0, 2.0, "Chappell 2018 / Iraki 2019", "10–14%"),
    "womens_figure":    ValueWithUncertainty(10.0, 2.0, "Hulmi 2017", "8–12%"),
    "womens_physique":  ValueWithUncertainty(8.0, 2.0, "Hulmi 2017", "6–10%"),
    "wellness":         ValueWithUncertainty(14.0, 2.0, "Chappell 2018", "12–16%"),
}

# ─── Legacy scalar helpers (retained for back-compat) ──────────────────
# Engines that only know the athlete's sex (not division) still need a
# reasonable stage BF. Male → Classic default (5%); female → Bikini
# default (12%) — the most common per-sex division.
STAGE_BF_PCT_MALE   = 5.0
STAGE_BF_PCT_FEMALE = 10.0


def stage_bf_pct_for_division(division: str) -> float:
    """Preferred API — division-specific stage BF."""
    key = (division or "").lower().replace(" ", "_")
    entry = STAGE_BF_PCT_BY_DIVISION.get(key)
    if entry is not None:
        return entry.value
    return STAGE_BF_PCT_MALE


def stage_bf_pct(sex: str) -> float:
    """Legacy API — sex-only fallback, used when division is unavailable."""
    return STAGE_BF_PCT_FEMALE if str(sex).lower().startswith("f") else STAGE_BF_PCT_MALE


# ---------------------------------------------------------------------------
# Offseason BF ceiling — trigger for mini-cut routing
# ---------------------------------------------------------------------------
# When the athlete's current BF exceeds the ceiling for their division, the
# planner routes into a 2-week mini-cut before the improvement cycle.
#
# Previous flat 16%/25% ceiling was too permissive per Helms 2014 / Iraki 2019,
# which converge on 8–12% M / 17–22% F as the "productive offseason" window.
# Going above 13% M / 22% F hurts partitioning.
OFFSEASON_BF_CEILING_BY_DIVISION: dict[str, ValueWithUncertainty] = {
    "mens_open":        ValueWithUncertainty(13.0, 1.0, "Helms 2014 / Iraki 2019", "alarm >13%"),
    "classic_physique": ValueWithUncertainty(13.0, 1.0, "Helms 2014 / Iraki 2019", "alarm >13%"),
    "mens_physique":    ValueWithUncertainty(12.0, 1.0, "Helms 2014 / Iraki 2019", "alarm >12%"),
    "womens_bikini":    ValueWithUncertainty(24.0, 2.0, "Chappell 2018 / Iraki 2019", ""),
    "womens_figure":    ValueWithUncertainty(20.0, 2.0, "Chappell 2018", ""),
    "womens_physique":  ValueWithUncertainty(18.0, 2.0, "Hulmi 2017", ""),
    "wellness":         ValueWithUncertainty(22.0, 2.0, "Chappell 2018", ""),
}
# Legacy scalars retained for modules that only know sex.
OFFSEASON_BF_CEILING_MALE   = 13.0
OFFSEASON_BF_CEILING_FEMALE = 22.0


def offseason_bf_ceiling_for_division(division: str) -> float:
    key = (division or "").lower().replace(" ", "_")
    entry = OFFSEASON_BF_CEILING_BY_DIVISION.get(key)
    if entry is not None:
        return entry.value
    return OFFSEASON_BF_CEILING_MALE


# ---------------------------------------------------------------------------
# Default-estimate BF when no measurement is logged
# ---------------------------------------------------------------------------
# For an advanced-natural population entering prep, Helms 2014 / Iraki 2019
# suggest 12% M / 20% F as the central offseason estimate — not the prior
# 15%/22% which over-estimates BF and under-estimates readiness.
FALLBACK_OFFSEASON_BF_MALE   = 12.0
FALLBACK_OFFSEASON_BF_FEMALE = 20.0


def fallback_offseason_bf_pct(sex: str) -> float:
    return (FALLBACK_OFFSEASON_BF_FEMALE
            if str(sex).lower().startswith("f")
            else FALLBACK_OFFSEASON_BF_MALE)


# ---------------------------------------------------------------------------
# Per-site lean-projection coefficients (legacy heuristic path)
# ---------------------------------------------------------------------------
# These multipliers model how much subcutaneous fat sits over each tape site.
# They are **priors** — no peer-reviewed derivation exists. The preferred
# girth-projection path is ISAK-anchored from skinfolds
# (see `engine1.girth_projection.project_lean`). This block remains for the
# BF-only fallback when no skinfold data is available.
#
# Prior source: Lohman "Advances in Body Composition Assessment" + Wang &
# Pierson anthropometry. Flagged as HEURISTIC_PRIOR so validation can
# recalibrate against a corpus.
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
SITE_LEAN_K_PROVENANCE = "Lohman / Wang-Pierson prior (HEURISTIC — pending corpus fit)"


def project_lean_girth(raw_cm: float, site: str, bf_pct: float | None) -> float:
    """Project a raw tape measurement down to stage-lean girth (BF-only path).

    Thin shim — dispatches to `engine1.girth_projection.project_lean_bf_only`
    which owns the canonical BF-linear implementation. New callers should
    use `girth_projection.project_lean(raw, site, skinfold_row, bf_pct)`
    instead, which supports ISAK + JP-derived paths.
    """
    # Lazy import: girth_projection imports from physio (SITE_LEAN_K).
    from app.engines.engine1.girth_projection import project_lean_bf_only
    return project_lean_bf_only(raw_cm, site, bf_pct)


# ---------------------------------------------------------------------------
# HQI staleness window
# ---------------------------------------------------------------------------
# Diagnostics older than this lose effective weight in readiness scoring.
# Currently a hard 90-day cutoff; follow-up will replace with a Gaussian
# decay w(Δt) = exp(−(Δt / 45)²) per the v2 doc §1.
HQI_FRESHNESS_DAYS = 90
HQI_FRESHNESS_PROVENANCE = "Operational prior — matches DEXA re-test intervals"


# ---------------------------------------------------------------------------
# Symmetry-score penalty multipliers
# ---------------------------------------------------------------------------
# How many points to deduct per unit of bilateral asymmetry (fractional
# deviation × multiplier). Recalibrated per v2 doc §10 based on IFBB pose
# visibility frequency. Previously used priors 600/600/550/300; the new
# values rebalance based on which poses the asymmetry appears in.
SYMMETRY_PENALTY_MULT: dict[str, float] = {
    "bicep":     650,   # double-bi exposes most-visible asymmetry
    "forearm":   500,   # less isolated than bicep
    "calf":      600,   # visible in every rear pose
    "thigh":     450,   # larger baseline (2% = more cm)
    "chest":     550,   # side-chest pose exposes
    "shoulders": 600,   # front-double-bi delt-cap asymmetry is heavily penalized
    "back":      500,   # partially hidden under lat spread
}
SYMMETRY_PENALTY_DEFAULT = 500
SYMMETRY_PENALTY_PROVENANCE = (
    "v2 doc §10 prior — IFBB pose-visibility weighted; pending corpus fit"
)


# ---------------------------------------------------------------------------
# Asymmetry threshold that triggers unilateral programming
# ---------------------------------------------------------------------------
# Previously absolute 1.5 cm — too small for a 70 cm thigh, too large
# for a 30 cm forearm. The v2 doc §1 corrects to a relative threshold.
# A 3.5% pair spread triggers bias; 2.5% for arms/calves where the eye
# is trained to spot asymmetry.
ASYMMETRY_UNILATERAL_CM = 1.5   # legacy absolute (deprecated — see relative)
ASYMMETRY_UNILATERAL_REL = 0.035
ASYMMETRY_UNILATERAL_REL_ARMS_CALVES = 0.025
ASYMMETRY_UNILATERAL_PROVENANCE = (
    "v2 doc §1; Pearson/Bazyler <5% normal-variation band in elite athletes"
)


# ---------------------------------------------------------------------------
# PhaseState — consolidated enum for previously stringly-typed phases
# ---------------------------------------------------------------------------
# The `prep_timeline.get_current_phase` return value, the `compute_macros`
# phase arg, and the `services/training` phase resolver all spoke strings.
# New code should use PhaseState; existing code keeps strings (values below
# match those strings exactly).
from enum import Enum


class PhaseState(str, Enum):
    OFFSEASON = "offseason"
    LEAN_BULK = "lean_bulk"
    MAINTAIN = "maintain"
    CUT = "cut"
    PEAK_WEEK = "peak_week"
    CONTEST = "contest"
    RESTORATION = "restoration"
    # PPM sub-phases
    PPM_ASSESSMENT = "ppm_assessment"
    PPM_ACCUMULATION = "ppm_accumulation"
    PPM_INTENSIFICATION = "ppm_intensification"
    PPM_DELOAD = "ppm_deload"
    PPM_CHECKPOINT = "ppm_checkpoint"
    PPM_MINI_CUT = "ppm_mini_cut"


# ---------------------------------------------------------------------------
# Provenance registry — any module can introspect where a constant came from
# ---------------------------------------------------------------------------
PROVENANCE_REGISTRY: dict[str, str] = {
    "STAGE_BF_PCT_BY_DIVISION":        "Helms 2014 / Iraki 2019 / Hulmi 2017 / Chappell 2018",
    "OFFSEASON_BF_CEILING_BY_DIVISION": "Helms 2014 / Iraki 2019",
    "FALLBACK_OFFSEASON_BF":            "Helms 2014 / Iraki 2019 central estimate",
    "SITE_LEAN_K":                      SITE_LEAN_K_PROVENANCE,
    "HQI_FRESHNESS_DAYS":               HQI_FRESHNESS_PROVENANCE,
    "SYMMETRY_PENALTY_MULT":            SYMMETRY_PENALTY_PROVENANCE,
    "ASYMMETRY_UNILATERAL_REL":         ASYMMETRY_UNILATERAL_PROVENANCE,
}
