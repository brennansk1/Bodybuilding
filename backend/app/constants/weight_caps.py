"""
Official IFBB Weight Cap Lookup Tables

Height-bracket weight caps for each division. Classic Physique and Men's Physique
use official IFBB Pro League limits. Men's Open (uncapped) and women's divisions
use virtual caps derived from Olympia/top-level competitor anthropometric data.

Usage:
    cap_kg = lookup_weight_cap(height_cm=188, division="classic_physique")
    target_lbm = cap_kg * 0.95   # assumes ~5% stage body fat
"""

from bisect import bisect_left


# ---------------------------------------------------------------------------
# Men's Open — no official cap; virtual caps from elite Open competitor data
# (Olympia top-10 averages by height bracket, 2018-2024)
# ---------------------------------------------------------------------------
_MENS_OPEN_CAPS: list[tuple[float, float]] = [
    (162.6, 100.2),
    (165.1, 103.0),
    (167.6, 106.1),
    (170.2, 108.9),
    (172.7, 111.6),
    (175.3, 115.7),
    (177.8, 120.2),
    (180.3, 124.3),
    (182.9, 128.8),
    (185.4, 132.4),
    (188.0, 137.0),
    (190.5, 141.1),
    (193.0, 145.1),
    (195.6, 149.2),
    (198.1, 152.9),
    (200.7, 156.9),
    (999.0, 161.0),
]

# ---------------------------------------------------------------------------
# Classic Physique — official IFBB Pro League weight limits (2024 rules)
# Source: Ground Truth audit; npcnewsonline.com/classic-physique;
# ifbbproleague.com.au ClassicPhysiqueHeightWeight.pdf
# ---------------------------------------------------------------------------
_CLASSIC_PHYSIQUE_CAPS: list[tuple[float, float]] = [
    (162.6, 75.7),
    (165.1, 78.0),
    (167.6, 80.3),
    (170.2, 82.6),
    (172.7, 84.8),
    (175.3, 88.0),
    (177.8, 91.6),
    (180.3, 94.8),
    (182.9, 98.4),
    (185.4, 101.6),
    (188.0, 105.2),
    (190.5, 108.4),
    (193.0, 111.6),
    (195.6, 114.8),
    (198.1, 117.9),
    (200.7, 121.1),
    (999.0, 124.3),
]

# ---------------------------------------------------------------------------
# Men's Physique — official IFBB Pro League weight limits
# ---------------------------------------------------------------------------
_MENS_PHYSIQUE_CAPS: list[tuple[float, float]] = [
    (162.6, 75.7),
    (165.1, 78.0),
    (167.6, 80.3),
    (170.2, 82.6),
    (172.7, 84.8),
    (175.3, 88.0),
    (177.8, 91.6),
    (180.3, 94.8),
    (182.9, 98.4),
    (185.4, 101.6),
    (188.0, 105.2),
    (190.5, 108.4),
    (193.0, 111.6),
    (195.6, 114.8),
    (198.1, 117.9),
    (200.7, 121.1),
    (999.0, 124.3),
]

# ---------------------------------------------------------------------------
# Women's Physique — virtual caps from elite competitor data
# ---------------------------------------------------------------------------
_WOMENS_PHYSIQUE_CAPS: list[tuple[float, float]] = [
    (152.4, 54.0),
    (154.9, 55.8),
    (157.5, 57.6),
    (160.0, 59.4),
    (162.6, 61.2),
    (165.1, 63.0),
    (167.6, 64.9),
    (170.2, 66.7),
    (172.7, 68.5),
    (175.3, 70.3),
    (177.8, 72.1),
    (180.3, 73.9),
    (182.9, 75.7),
    (999.0, 77.6),
]

# ---------------------------------------------------------------------------
# Women's Figure — virtual caps
# ---------------------------------------------------------------------------
_WOMENS_FIGURE_CAPS: list[tuple[float, float]] = [
    (152.4, 51.3),
    (154.9, 52.6),
    (157.5, 54.0),
    (160.0, 55.3),
    (162.6, 56.7),
    (165.1, 58.1),
    (167.6, 59.4),
    (170.2, 60.8),
    (172.7, 62.1),
    (175.3, 63.5),
    (177.8, 64.9),
    (180.3, 66.2),
    (182.9, 67.6),
    (999.0, 68.9),
]

# ---------------------------------------------------------------------------
# Women's Bikini — virtual caps (lightest division)
# ---------------------------------------------------------------------------
_WOMENS_BIKINI_CAPS: list[tuple[float, float]] = [
    (152.4, 48.5),
    (154.9, 49.4),
    (157.5, 50.3),
    (160.0, 51.3),
    (162.6, 52.2),
    (165.1, 53.1),
    (167.6, 54.0),
    (170.2, 54.9),
    (172.7, 55.8),
    (175.3, 56.7),
    (177.8, 57.6),
    (180.3, 58.5),
    (182.9, 59.4),
    (999.0, 60.3),
]


# ---------------------------------------------------------------------------
# Lookup registry
# ---------------------------------------------------------------------------
_DIVISION_CAP_TABLES: dict[str, list[tuple[float, float]]] = {
    "mens_open": _MENS_OPEN_CAPS,
    "classic_physique": _CLASSIC_PHYSIQUE_CAPS,
    "mens_physique": _MENS_PHYSIQUE_CAPS,
    "womens_physique": _WOMENS_PHYSIQUE_CAPS,
    "womens_figure": _WOMENS_FIGURE_CAPS,
    "womens_bikini": _WOMENS_BIKINI_CAPS,
}


def lookup_weight_cap(height_cm: float, division: str) -> float:
    """
    Look up the stage weight cap (kg) for a given height and division.

    Uses binary search on height brackets. Returns the cap for the
    smallest bracket that contains the athlete's height.

    Args:
        height_cm: athlete height in centimeters
        division: competition division key

    Returns:
        Stage weight cap in kg
    """
    key = division.lower().replace(" ", "_")
    table = _DIVISION_CAP_TABLES.get(key, _MENS_OPEN_CAPS)

    # Find the first bracket where max_height >= athlete height
    heights = [row[0] for row in table]
    idx = bisect_left(heights, height_cm)
    idx = min(idx, len(table) - 1)

    return table[idx][1]


def lookup_target_lbm(height_cm: float, division: str, stage_bf_pct: float = 5.0) -> float:
    """
    Compute target lean body mass from the division weight cap.

    Target_LBM = Weight_Cap × (1 - stage_bf_fraction)

    For most competitive divisions this means ×0.95 (assuming 5% stage BF).
    """
    cap = lookup_weight_cap(height_cm, division)
    return round(cap * (1.0 - stage_bf_pct / 100.0), 2)
