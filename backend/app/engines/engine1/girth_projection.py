from __future__ import annotations

"""
Girth Projection — ISAK-anchored lean-circumference stripping

Converts a raw tape measurement (at current BF) to what that site would
measure at stage leanness. Two paths by precedence:

  1. Primary (ISAK):
         lean_cm = raw_cm − π × (skinfold_mm / 10)
     Requires a SkinfoldMeasurement row. The formula derives from the
     corrected-girth model: a subcutaneous fat sleeve of thickness
     `skinfold_mm` reduces circumference by π × skinfold.
     Sources: ISAK manual, Heymsfield et al. 1982 (Am J Clin Nutr
     36:680-690), Martin et al. 1993 (JRCSR).

  2. Fallback (JP-derived):
         estimated_skinfold = total_bf_pct × distribution_weight_site × const
         lean_cm            = raw − π × (estimated_skinfold / 10)
     When no skinfold row exists, back-estimate per-site mm from total
     BF% using Jackson–Pollock 7-site distribution ratios.
     Source: Jackson & Pollock 1978 (Br J Nutr 40:497-504).

  3. Last resort (BF-linear — legacy path):
         lean_cm = raw × (1 − k_site × (bf_pct − 5) / 100)
     Kept for back-compat (`physio.project_lean_girth`). HEURISTIC prior.

All paths apply a physiological floor: `lean_cm ≥ raw × 0.85`. A single
tape site can't strip below the athlete's stage leanness no matter what
the skinfold implies.

The public API returns both the projected value AND the method used so
downstream (muscle_gaps, aesthetic_vector) can surface confidence.
"""

import math

from app.constants.physio import SITE_LEAN_K


# ---------------------------------------------------------------------------
# Tape-site → skinfold-site mapping
# ---------------------------------------------------------------------------
# When a given tape site has no direct skinfold, use an anatomical neighbor
# with a scaling factor. Sources per doc §5 (anthropometric-neighbor mapping):
#   - neck       ← subscapular × 0.6 (cervical subq is thin relative to torso)
#   - forearm    ← tricep × 0.7
#   - calf       ← calf skinfold (preferred) or thigh × 0.8
#   - shoulders  ← mean(subscapular, chest × 0.5)
#   - hips       ← suprailiac
#   - back_width ← subscapular + chest × 0.5
TAPE_TO_SKINFOLD_MAP: dict[str, dict] = {
    "chest":      {"primary": "chest"},
    "waist":      {"primary": ("abdominal", "suprailiac"), "combine": "mean"},
    "thigh":      {"primary": "thigh"},
    "bicep":      {"primary": "bicep", "fallback": "tricep"},  # bicep skinfold column exists
    "forearm":    {"primary": "tricep", "scale": 0.7},
    "calf":       {"primary": "calf", "fallback": "thigh", "fallback_scale": 0.8},
    "neck":       {"primary": "subscapular", "scale": 0.6},
    "shoulders":  {"primary": ("subscapular", "chest"), "combine": "shoulders"},
    "hips":       {"primary": "suprailiac"},
    "back_width": {"primary": ("subscapular", "chest"), "combine": "back"},
}


# ---------------------------------------------------------------------------
# Jackson-Pollock 7-site distribution weights (female)
# Each weight is the fraction of total BF this site's fat contributes under
# the JP model. Used to back-estimate per-site mm from total BF%.
#
# We publish an M and F variant because JP fat distribution is sex-dependent.
# Source: Jackson & Pollock 1978, Jackson et al. 1980.
# ---------------------------------------------------------------------------
_JP_DISTRIBUTION_MALE: dict[str, float] = {
    "chest":       0.18,
    "abdominal":   0.20,
    "thigh":       0.18,
    "tricep":      0.12,
    "subscapular": 0.12,
    "suprailiac":  0.10,
    "midaxillary": 0.10,
}
_JP_DISTRIBUTION_FEMALE: dict[str, float] = {
    "tricep":      0.20,
    "suprailiac":  0.18,
    "thigh":       0.18,
    "abdominal":   0.12,
    "chest":       0.10,
    "subscapular": 0.12,
    "midaxillary": 0.10,
}

# Conversion constant: total BF% × distribution weight = per-site mm (roughly)
# Calibrated so that a 15% BF male produces ~9mm tricep, ~13mm abdominal —
# empirically typical from JP calibration studies.
_BF_PCT_TO_MM_SCALE = 4.5

# Physiological floor: a tape site cannot project below 85% of raw.
_LEAN_FLOOR_MULT = 0.85


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def project_lean(
    raw_cm: float,
    site: str,
    skinfold_row=None,
    bf_pct: float | None = None,
    sex: str = "male",
) -> dict:
    """Preferred lean-girth projection API.

    Args:
        raw_cm: tape measurement at current BF
        site: one of {neck, shoulders, chest, bicep, forearm, waist, hips,
              thigh, calf, back_width}
        skinfold_row: a SkinfoldMeasurement-like object (has `chest`,
                      `tricep`, `thigh`, etc. attributes) or dict, or None
        bf_pct: total body fat % (fallback when no skinfold_row)
        sex: for JP distribution weights

    Returns:
        {lean_cm: float, method: "isak_skinfold" | "jp_derived" | "bf_linear"}
    """
    if raw_cm is None or raw_cm <= 0:
        return {"lean_cm": 0.0, "method": "invalid_input"}

    # Primary — ISAK stripping from a real skinfold reading
    if skinfold_row is not None:
        mm = _resolve_skinfold_mm(site, skinfold_row)
        if mm is not None and mm > 0:
            lean = raw_cm - math.pi * (mm / 10.0)
            return {
                "lean_cm": round(max(lean, raw_cm * _LEAN_FLOOR_MULT), 2),
                "method": "isak_skinfold",
                "skinfold_mm": round(mm, 1),
            }

    # Fallback — JP-derived per-site mm from total BF%
    if bf_pct is not None and bf_pct > 0:
        mm_est = _estimate_skinfold_from_bf(site, bf_pct, sex)
        if mm_est is not None and mm_est > 0:
            lean = raw_cm - math.pi * (mm_est / 10.0)
            return {
                "lean_cm": round(max(lean, raw_cm * _LEAN_FLOOR_MULT), 2),
                "method": "jp_derived",
                "skinfold_mm_estimated": round(mm_est, 1),
            }

    # Last resort — BF-linear (legacy heuristic)
    lean = project_lean_bf_only(raw_cm, site, bf_pct)
    return {"lean_cm": round(lean, 2), "method": "bf_linear"}


def project_lean_bf_only(raw_cm: float, site: str, bf_pct: float | None) -> float:
    """Legacy BF-linear path, identical to the original physio.project_lean_girth.

    Kept so `physio.project_lean_girth` can dispatch here with preserved
    behavior for callers that don't have skinfold context.
    """
    if raw_cm is None or raw_cm <= 0:
        return 0.0
    if bf_pct is None or bf_pct <= 5.0:
        return float(raw_cm)
    k = SITE_LEAN_K.get(site, 0.45)
    excess_bf = max(0.0, bf_pct - 5.0)
    return float(raw_cm) * (1.0 - k * excess_bf / 100.0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _get_skinfold_attr(skinfold_row, attr_name: str) -> float | None:
    """Handle both SQLAlchemy objects and dicts for skinfold data."""
    if skinfold_row is None:
        return None
    if isinstance(skinfold_row, dict):
        v = skinfold_row.get(attr_name)
    else:
        v = getattr(skinfold_row, attr_name, None)
    if v is None:
        return None
    try:
        fv = float(v)
        return fv if fv > 0 else None
    except (TypeError, ValueError):
        return None


def _resolve_skinfold_mm(site: str, skinfold_row) -> float | None:
    """Map a tape site to a skinfold mm reading per TAPE_TO_SKINFOLD_MAP."""
    mapping = TAPE_TO_SKINFOLD_MAP.get(site)
    if not mapping:
        return None

    primary = mapping.get("primary")

    # Combined sites (waist = mean of abdominal+suprailiac; shoulders/back)
    if isinstance(primary, tuple):
        combine = mapping.get("combine", "mean")
        vals = [_get_skinfold_attr(skinfold_row, s) for s in primary]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        if combine == "mean":
            return sum(vals) / len(vals)
        if combine == "shoulders":
            # mean(subscapular, chest × 0.5)
            sub = _get_skinfold_attr(skinfold_row, "subscapular")
            chest = _get_skinfold_attr(skinfold_row, "chest")
            parts = [v for v in [sub, (chest * 0.5) if chest else None] if v is not None]
            return sum(parts) / len(parts) if parts else None
        if combine == "back":
            # subscapular + chest × 0.5
            sub = _get_skinfold_attr(skinfold_row, "subscapular") or 0.0
            chest = _get_skinfold_attr(skinfold_row, "chest") or 0.0
            return sub + chest * 0.5 if (sub or chest) else None

    # Single-site primary, optional fallback + scaling
    val = _get_skinfold_attr(skinfold_row, primary)
    if val is None:
        fb = mapping.get("fallback")
        if fb:
            val = _get_skinfold_attr(skinfold_row, fb)
            if val is not None:
                val *= mapping.get("fallback_scale", 1.0)
    else:
        val *= mapping.get("scale", 1.0)
    return val


def _estimate_skinfold_from_bf(site: str, bf_pct: float, sex: str) -> float | None:
    """Back-estimate per-site mm from total BF% using JP distribution weights."""
    mapping = TAPE_TO_SKINFOLD_MAP.get(site)
    if not mapping:
        return None
    table = _JP_DISTRIBUTION_FEMALE if str(sex).lower().startswith("f") else _JP_DISTRIBUTION_MALE

    primary = mapping.get("primary")

    if isinstance(primary, tuple):
        combine = mapping.get("combine", "mean")
        mms = [bf_pct * table.get(s, 0.12) * _BF_PCT_TO_MM_SCALE for s in primary]
        if combine == "mean":
            return sum(mms) / len(mms)
        if combine == "shoulders":
            sub = bf_pct * table.get("subscapular", 0.12) * _BF_PCT_TO_MM_SCALE
            chest = bf_pct * table.get("chest", 0.10) * _BF_PCT_TO_MM_SCALE * 0.5
            return (sub + chest) / 2
        if combine == "back":
            sub = bf_pct * table.get("subscapular", 0.12) * _BF_PCT_TO_MM_SCALE
            chest = bf_pct * table.get("chest", 0.10) * _BF_PCT_TO_MM_SCALE * 0.5
            return sub + chest

    # Single-site
    weight = table.get(primary, 0.10)
    mm = bf_pct * weight * _BF_PCT_TO_MM_SCALE
    mm *= mapping.get("scale", 1.0)
    return mm
