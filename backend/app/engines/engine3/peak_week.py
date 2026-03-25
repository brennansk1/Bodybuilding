from __future__ import annotations

"""
Peak Week Protocol Engine

Generates a 7-day carbohydrate, water, and sodium manipulation protocol
for competition peak week.

Standard protocol (show on Saturday):
  Mon: Depletion (low carb, moderate sodium, normal water)
  Tue: Depletion (very low carb, low sodium, normal water)
  Wed: Moderate (transition — small carb increase, low sodium)
  Thu: Load day 1 (high carb, low sodium, reduced water)
  Fri: Load day 2 (high carb, very low sodium, reduced water)
  Sat: Show day (moderate carb, very low sodium, controlled water)
  Sun: Recovery (moderate carb, normal eating resumes)

Carbohydrate targets are derived from lean body mass (LBM) to scale
appropriately for athletes of different sizes.
"""

from datetime import date, timedelta


# Grams of carbs per kg LBM per day for each phase of the protocol
_DEPLETION_CARBS_PER_KG = 0.5   # Mon-Tue
_MODERATE_CARBS_PER_KG  = 2.0   # Wed (transition)
_LOAD_CARBS_PER_KG      = 5.0   # Thu-Fri (load)
_SHOW_CARBS_PER_KG      = 3.0   # Sat (hold)
_RECOVERY_CARBS_PER_KG  = 3.5   # Sun (recover)

# Sodium targets (mg/day)
_SODIUM_NORMAL   = 2300
_SODIUM_LOW      = 1200
_SODIUM_VERY_LOW = 500

# Water targets (mL/day) — show day is tightly controlled
_WATER_NORMAL    = 4000
_WATER_MODERATE  = 3000
_WATER_REDUCED   = 2000


def compute_peak_week_protocol(
    lean_mass_kg: float,
    show_date: date | None = None,
    division: str = "mens_open",
) -> list[dict]:
    """
    Generate a 7-day peak-week protocol scaled to the athlete's lean mass.

    Args:
        lean_mass_kg: Athlete's lean body mass in kg (body_weight × (1 - bf%)).
                      Used to scale carbohydrate targets.
        show_date: Date of the competition. If provided, each day in the
                   protocol will have an absolute date attached.
                   Assumes show is on ``show_date`` (Saturday slot).

    Returns:
        List of 7 dicts, one per day, each containing:
          - ``day``: Day label (e.g. ``"Monday"``)
          - ``date``: ISO date string if show_date provided, else None.
          - ``protocol_day``: Protocol stage name.
          - ``carbs_g``: Target carbohydrate grams.
          - ``protein_g``: Protein target (stays high throughout — 2.2 g/kg LBM).
          - ``fat_g``: Fat target (minimal on load days).
          - ``sodium_mg``: Sodium target (mg).
          - ``water_ml``: Water intake target (mL).
          - ``notes``: Key coaching cues for this day.
    """
    lbm = max(40.0, lean_mass_kg)  # floor for safety
    protein_g = round(lbm * 2.2, 0)

    # Division-specific peak week intensity
    div_key = division.lower().replace(" ", "_")
    _AGGRESSIVE_DIVISIONS = {"mens_open", "classic_physique", "womens_physique", "womens_figure"}
    _GENTLE_DIVISIONS = {"womens_bikini", "mens_physique"}

    aggressive = div_key in _AGGRESSIVE_DIVISIONS
    gentle = div_key in _GENTLE_DIVISIONS

    # Water loading protocol: aggressive divisions load heavily then cut;
    # gentle divisions taper gradually and maintain moderate hydration
    if aggressive:
        # Saturday: minimum 2800 mL — joint lubrication, pump preservation, blood volume
        # Cutting below 2.5L on stage day risks cramping and vasovagal events in hot staging areas
        water_schedule = [8000, 8000, 6000, 3000, 2500, 2800, 4000]
    elif gentle:
        water_schedule = [5000, 5000, 4500, 4000, 3500, 3000, 4000]
    else:
        water_schedule = [6000, 6000, 5000, 3500, 3000, 2500, 4000]

    # Sodium protocol: maintain sodium during carb load for SGLT1 glucose transport
    # Ratio targets: 4:1 to 5:1 Na:K during carb load days
    if aggressive:
        sodium_schedule = [2000, 1500, 1000, 1500, 1200, 800, 2300]
    elif gentle:
        sodium_schedule = [2300, 2300, 2000, 1800, 1500, 1200, 2300]
    else:
        sodium_schedule = [2300, 2000, 1500, 1500, 1200, 1000, 2300]

    # Start Monday of peak week (6 days before show)
    if show_date:
        # Find the Monday before show_date
        show_weekday = show_date.weekday()
        monday = show_date - timedelta(days=(show_weekday if show_weekday < 6 else 6))
    else:
        monday = None

    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    day_configs = [
        {  # Monday — Depletion Day 1
            "protocol_day": "depletion_1",
            "carbs_factor": _DEPLETION_CARBS_PER_KG,
            "fat_g": round(lbm * 0.8, 0),
            "sodium_mg": _SODIUM_LOW,
            "water_ml": _WATER_NORMAL,
            "notes": (
                "Full depletion. Keep carbs very low to deplete muscle glycogen. "
                "Maintain high protein. Train with moderate-volume full-body pump work "
                "to accelerate depletion. Normal water intake."
            ),
        },
        {  # Tuesday — Depletion Day 2
            "protocol_day": "depletion_2",
            "carbs_factor": _DEPLETION_CARBS_PER_KG * 0.6,
            "fat_g": round(lbm * 0.8, 0),
            "sodium_mg": _SODIUM_VERY_LOW,
            "water_ml": _WATER_NORMAL,
            "notes": (
                "Deepest depletion day. Carbs at their lowest. "
                "Begin cutting sodium to prepare for the carb load. "
                "Normal water intake — do not restrict water today."
            ),
        },
        {  # Wednesday — Transition
            "protocol_day": "transition",
            "carbs_factor": _MODERATE_CARBS_PER_KG,
            "fat_g": round(lbm * 0.6, 0),
            "sodium_mg": _SODIUM_LOW,
            "water_ml": _WATER_MODERATE,
            "notes": (
                "Transition day. Begin introducing carbs — muscles should "
                "be primed to absorb glycogen super-compensate. "
                "Keep sodium low. Slightly reduce water."
            ),
        },
        {  # Thursday — Load Day 1
            "protocol_day": "load_1",
            "carbs_factor": _LOAD_CARBS_PER_KG,
            "fat_g": round(lbm * 0.4, 0),
            "sodium_mg": _SODIUM_VERY_LOW,
            "water_ml": _WATER_REDUCED,
            "notes": (
                "Primary carb load. High-GI carbs from rice, white potato, "
                "and bananas. Keep fat extremely low — fat inhibits glycogen storage. "
                "Sodium very low. Reduce water intake."
            ),
        },
        {  # Friday — Load Day 2 / Final Adjustments
            "protocol_day": "load_2",
            "carbs_factor": _LOAD_CARBS_PER_KG * 0.8,
            "fat_g": round(lbm * 0.3, 0),
            "sodium_mg": _SODIUM_VERY_LOW,
            "water_ml": _WATER_REDUCED,
            "notes": (
                "Continue carb load at slightly lower carbs. "
                "Assess condition by late evening — if looking flat, "
                "add 50-75g carbs before sleep. If looking full and tight, hold. "
                "Virtually no sodium. Water carefully controlled."
            ),
        },
        {  # Saturday — Show Day
            "protocol_day": "show_day",
            "carbs_factor": _SHOW_CARBS_PER_KG,
            "fat_g": round(lbm * 0.3, 0),
            "sodium_mg": _SODIUM_VERY_LOW,
            "water_ml": _WATER_REDUCED,
            "notes": (
                "Show day. Small, easily digestible carb meals every 90 min "
                "starting 3 h before pre-judging. Avoid bloating foods. "
                "Pump up backstage with 10-15 min of light resistance work. "
                "Sip water — do not restrict completely."
            ),
        },
        {  # Sunday — Recovery
            "protocol_day": "recovery",
            "carbs_factor": _RECOVERY_CARBS_PER_KG,
            "fat_g": round(lbm * 0.8, 0),
            "sodium_mg": _SODIUM_NORMAL,
            "water_ml": _WATER_NORMAL,
            "notes": (
                "Recovery day. Reintroduce normal sodium and water. "
                "Enjoy a celebratory meal. Return to normal eating — "
                "your body is primed for growth immediately post-show."
            ),
        },
    ]

    # Apply division-specific schedules to day configs
    for i, config in enumerate(day_configs):
        config["sodium_mg"] = sodium_schedule[i]
        config["water_ml"] = water_schedule[i]
        # Potassium: maintain Na:K ratio on load days
        if config["protocol_day"] in ("load_1", "load_2", "show_day"):
            config["potassium_mg"] = round(sodium_schedule[i] / 4.5)
        else:
            config["potassium_mg"] = 3500
        # Division note for gentle divisions
        if gentle and config["protocol_day"] in ("load_1", "load_2", "show_day"):
            config["notes"] += (
                " Division protocol: maintain fuller, softer appearance. Do not over-dry."
            )

    protocol = []
    for i, (day_name, config) in enumerate(zip(days_of_week, day_configs)):
        carbs_g = round(lbm * config["carbs_factor"], 0)
        day_date = str(monday + timedelta(days=i)) if monday else None

        protocol.append({
            "day": day_name,
            "date": day_date,
            "protocol_day": config["protocol_day"],
            "carbs_g": int(carbs_g),
            "protein_g": int(protein_g),
            "fat_g": int(config["fat_g"]),
            "sodium_mg": config["sodium_mg"],
            "water_ml": config["water_ml"],
            "potassium_mg": config["potassium_mg"],
            "total_calories": int(carbs_g * 4 + protein_g * 4 + config["fat_g"] * 9),
            "notes": config["notes"],
        })

    return protocol


# ---------------------------------------------------------------------------
# Reactive Peak Week Controller
# ---------------------------------------------------------------------------
# Pro coaches don't follow a static plan — they react to how the athlete
# looks each morning. This controller takes a visual state check-in and
# adjusts the remaining day's macros in real-time.

_PEAK_WEEK_STATES = {"flat", "spilled", "peaked", "overshot"}


def adjust_peak_day_for_condition(
    day_protocol: dict,
    condition: str,
) -> dict:
    """Reactively adjust a single peak-week day based on morning visual check-in.

    This replaces the static Friday-only adjustment with a fully reactive
    system that mirrors how elite coaches audible during peak week.

    Args:
        day_protocol: A single day dict from :func:`compute_peak_week_protocol`.
        condition: Athlete's visual state — one of:
            - ``"flat"``: Muscles lack volume, vascularity low, skin tight but
              depleted. Action: increase carbs +25%, add sodium +400mg.
            - ``"spilled"``: Blurry, holding subcutaneous water, distended.
              Action: cut carbs 50%, hold water steady, add potassium +500mg.
            - ``"peaked"``: Full, dry, vascular — the ideal state.
              Action: freeze current intake, coast on maintenance.

    Returns:
        Adjusted day_protocol dict (new copy, original not mutated).
    """
    condition_key = condition.strip().lower()
    if condition_key not in _PEAK_WEEK_STATES:
        return dict(day_protocol)  # unknown state — return unchanged

    result = dict(day_protocol)

    if condition_key == "flat":
        # Muscles are depleted — push more glycogen in
        result["carbs_g"] = int(round(day_protocol["carbs_g"] * 1.25))
        result["sodium_mg"] = day_protocol["sodium_mg"] + 400
        result["notes"] = (
            "REACTIVE ADJUSTMENT (FLAT): Carbs increased 25% to drive glycogen "
            "into depleted muscles. Sodium bumped +400mg to facilitate SGLT1 "
            "glucose co-transport across intestinal lumen. Monitor for filling "
            "over next 4-6 hours."
        )

    elif condition_key == "spilled":
        # Holding subcutaneous water — dry out
        result["carbs_g"] = int(round(day_protocol["carbs_g"] * 0.50))
        # Water stays steady — do NOT restrict further (dangerous)
        result["potassium_mg"] = day_protocol.get("potassium_mg", 3500) + 500
        result["notes"] = (
            "REACTIVE ADJUSTMENT (SPILLED): Carbs slashed 50% to halt glycogen "
            "overflow causing subcutaneous water retention. Potassium increased "
            "+500mg to pull fluid intracellularly via Na/K-ATPase pump. Water "
            "intake held steady — further restriction risks cramping and "
            "dangerous dehydration."
        )

    elif condition_key == "peaked":
        # Perfect condition — change nothing
        result["notes"] = (
            "REACTIVE ADJUSTMENT (PEAKED): Athlete is full, dry, and vascular. "
            "Freezing current intake — coast on these exact macros until stage. "
            "No further manipulation needed. Light pump work only."
        )

    elif condition_key == "overshot":
        # So full that 3D roundness is lost — muscle looks bulbous, not peaked
        # Slightly different from "spilled" — water needs to shift intracellularly
        result["carbs_g"] = int(round(day_protocol["carbs_g"] * 0.60))
        result["water_ml"] = day_protocol["water_ml"] + 500  # increase water to pull subcutaneous fluid in
        result["potassium_mg"] = day_protocol.get("potassium_mg", 3500) + 800
        result["sodium_mg"] = max(400, day_protocol["sodium_mg"] - 200)
        result["notes"] = (
            "REACTIVE ADJUSTMENT (OVERSHOT): Muscle appears bulbous/round — glycogen "
            "has overflowed and is sitting interstitially rather than intracellularly. "
            "Carbs reduced 40%. Water INCREASED +500mL + potassium +800mg to pull fluid "
            "intracellularly via Na/K-ATPase pump. Reduce sodium slightly. "
            "This is NOT the same as 'spilled' — do not restrict water."
        )

    # Recalculate calories
    result["total_calories"] = int(
        result["carbs_g"] * 4 + result["protein_g"] * 4 + result["fat_g"] * 9
    )

    return result


def apply_reactive_peak_week(
    protocol: list[dict],
    daily_conditions: dict[str, str],
) -> list[dict]:
    """Apply reactive adjustments across a full peak week protocol.

    Args:
        protocol: 7-day protocol from :func:`compute_peak_week_protocol`.
        daily_conditions: Mapping of date string (ISO) or day name to
            condition state (``"flat"``, ``"spilled"``, ``"peaked"``).
            Days not in this dict are left unchanged.

    Returns:
        Adjusted protocol (new list, originals not mutated).
    """
    adjusted = []
    for day in protocol:
        key = day.get("date") or day["day"]
        condition = daily_conditions.get(key) or daily_conditions.get(day["day"])
        if condition:
            adjusted.append(adjust_peak_day_for_condition(day, condition))
        else:
            adjusted.append(dict(day))
    return adjusted
