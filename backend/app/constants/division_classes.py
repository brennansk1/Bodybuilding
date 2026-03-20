from __future__ import annotations

"""
Division Class Estimation Tables

Routes athletes into their likely competition class based on height and/or
weight. Returns the class name and weight limits for dashboard display.

Classes are division-specific:
  - Classic Physique: height-based classes (A through Open)
  - Men's Physique: height-based classes (A through D)
  - Men's Open: weight-based classes (varies by federation)
  - Women's divisions: height-based classes
"""


# ---------------------------------------------------------------------------
# Classic Physique — IFBB Pro League height classes
# ---------------------------------------------------------------------------
_CLASSIC_PHYSIQUE_CLASSES: list[dict] = [
    {"class": "A", "label": "Class A", "max_height_cm": 170.0, "max_weight_kg": 82.0},
    {"class": "B", "label": "Class B", "max_height_cm": 175.0, "max_weight_kg": 89.0},
    {"class": "C", "label": "Class C", "max_height_cm": 180.0, "max_weight_kg": 96.0},
    {"class": "D", "label": "Class D", "max_height_cm": 188.0, "max_weight_kg": 107.0},
    {"class": "Open", "label": "Open Class", "max_height_cm": 999.0, "max_weight_kg": 125.0},
]

# ---------------------------------------------------------------------------
# Men's Physique — IFBB height classes
# ---------------------------------------------------------------------------
_MENS_PHYSIQUE_CLASSES: list[dict] = [
    {"class": "A", "label": "Class A", "max_height_cm": 170.0, "max_weight_kg": None},
    {"class": "B", "label": "Class B", "max_height_cm": 175.0, "max_weight_kg": None},
    {"class": "C", "label": "Class C", "max_height_cm": 180.0, "max_weight_kg": None},
    {"class": "D", "label": "Class D", "max_height_cm": 999.0, "max_weight_kg": None},
]

# ---------------------------------------------------------------------------
# Men's Open — NPC/IFBB weight classes (amateur)
# ---------------------------------------------------------------------------
_MENS_OPEN_CLASSES: list[dict] = [
    {"class": "Bantamweight", "label": "Bantamweight", "max_weight_kg": 65.8},
    {"class": "Lightweight", "label": "Lightweight", "max_weight_kg": 70.3},
    {"class": "Middleweight", "label": "Middleweight", "max_weight_kg": 79.4},
    {"class": "Light-Heavyweight", "label": "Light-Heavyweight", "max_weight_kg": 88.5},
    {"class": "Heavyweight", "label": "Heavyweight", "max_weight_kg": 102.1},
    {"class": "Super-Heavyweight", "label": "Super-Heavyweight", "max_weight_kg": 999.0},
]

# ---------------------------------------------------------------------------
# Women's Figure — IFBB height classes
# ---------------------------------------------------------------------------
_WOMENS_FIGURE_CLASSES: list[dict] = [
    {"class": "A", "label": "Class A", "max_height_cm": 158.0, "max_weight_kg": None},
    {"class": "B", "label": "Class B", "max_height_cm": 163.0, "max_weight_kg": None},
    {"class": "C", "label": "Class C", "max_height_cm": 168.0, "max_weight_kg": None},
    {"class": "D", "label": "Class D", "max_height_cm": 173.0, "max_weight_kg": None},
    {"class": "Open", "label": "Open Class", "max_height_cm": 999.0, "max_weight_kg": None},
]

# ---------------------------------------------------------------------------
# Women's Bikini — IFBB height classes
# ---------------------------------------------------------------------------
_WOMENS_BIKINI_CLASSES: list[dict] = [
    {"class": "A", "label": "Class A", "max_height_cm": 158.0, "max_weight_kg": None},
    {"class": "B", "label": "Class B", "max_height_cm": 163.0, "max_weight_kg": None},
    {"class": "C", "label": "Class C", "max_height_cm": 168.0, "max_weight_kg": None},
    {"class": "D", "label": "Class D", "max_height_cm": 173.0, "max_weight_kg": None},
    {"class": "Open", "label": "Open Class", "max_height_cm": 999.0, "max_weight_kg": None},
]

# ---------------------------------------------------------------------------
# Women's Physique — IFBB height classes
# ---------------------------------------------------------------------------
_WOMENS_PHYSIQUE_CLASSES: list[dict] = [
    {"class": "A", "label": "Class A", "max_height_cm": 163.0, "max_weight_kg": None},
    {"class": "B", "label": "Class B", "max_height_cm": 168.0, "max_weight_kg": None},
    {"class": "Open", "label": "Open Class", "max_height_cm": 999.0, "max_weight_kg": None},
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_DIVISION_CLASS_TABLES: dict[str, list[dict]] = {
    "mens_open": _MENS_OPEN_CLASSES,
    "classic_physique": _CLASSIC_PHYSIQUE_CLASSES,
    "mens_physique": _MENS_PHYSIQUE_CLASSES,
    "womens_physique": _WOMENS_PHYSIQUE_CLASSES,
    "womens_figure": _WOMENS_FIGURE_CLASSES,
    "womens_bikini": _WOMENS_BIKINI_CLASSES,
}


def estimate_class(
    height_cm: float,
    division: str,
    body_weight_kg: float | None = None,
) -> dict:
    """
    Estimate the athlete's competition class based on height and/or weight.

    Returns:
        {
            "class": str,          # e.g. "D", "Heavyweight"
            "label": str,          # e.g. "Class D", "Heavyweight"
            "max_weight_kg": float | None,  # weight limit for this class
            "max_height_cm": float | None,  # height limit for this class
            "division": str,
        }
    """
    key = division.lower().replace(" ", "_")
    table = _DIVISION_CLASS_TABLES.get(key, _CLASSIC_PHYSIQUE_CLASSES)

    # Men's Open uses weight-based routing
    if key == "mens_open" and body_weight_kg is not None:
        for entry in table:
            if body_weight_kg <= entry["max_weight_kg"]:
                return {**entry, "division": division}
        return {**table[-1], "division": division}

    # All other divisions use height-based routing
    for entry in table:
        if height_cm <= entry.get("max_height_cm", 999.0):
            return {**entry, "division": division}

    return {**table[-1], "division": division}
