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
            "total_calories": int(carbs_g * 4 + protein_g * 4 + config["fat_g"] * 9),
            "notes": config["notes"],
        })

    return protocol
