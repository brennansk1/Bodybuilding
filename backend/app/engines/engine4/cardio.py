"""
Engine 4 — Cardio & NEAT Controller

Pure math module for managing energy expenditure through cardio
periodization and Non-Exercise Activity Thermogenesis (NEAT) tracking.
No DB or HTTP imports.

Philosophy: An elite prep coach manipulates energy EXPENDITURE before
dropping calories to the thermodynamic floor.  This engine intercepts
Engine 3's caloric reduction pathway and mandates cardio/NEAT increases
when the athlete is approaching minimum viable intake.

Three subroutines:
  4.1  Energy Flux Model — keep food high, push expenditure higher
  4.2  NEAT Tracking — step count titration across phases
  4.3  Active Cardio Periodization — HIIT in offseason, LISS-only late prep
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 4.1  Energy Flux Model
# ---------------------------------------------------------------------------
# The "Energy Flux" principle: maintain higher food intake to preserve
# metabolic rate and training intensity, while increasing expenditure
# to create the deficit.  Only drop food as a last resort.

# Thermodynamic floor thresholds (kcal/day) — Engine 4 intercepts BEFORE
# Engine 3 drops below these values
_FLOOR_INTERCEPT = {
    "male": 1800,    # intercept 300 kcal above Engine 3's 1500 floor
    "female": 1450,  # intercept 250 kcal above Engine 3's 1200 floor
}

# Cardio calories per session by modality (approximate, 30-min session)
_CARDIO_BURN_ESTIMATES = {
    "liss_incline_walk": 200,
    "liss_stairmaster": 250,
    "liss_cycling": 220,
    "zone2_cycling": 280,
    "hiit_sprint": 350,
    "hiit_rowing": 320,
    "hiit_cycling": 300,
    "steady_state_elliptical": 230,
}


def compute_energy_flux_prescription(
    current_calories: float,
    target_deficit: float,
    sex: str,
    current_cardio_sessions: int = 0,
    current_cardio_minutes: int = 0,
    weeks_in_deficit: int = 0,
    phase: str = "cut",
) -> dict:
    """Determine whether to reduce food or increase cardio expenditure.

    The Energy Flux model prioritises maintaining food intake above the
    intercept threshold.  When calories are approaching the floor, this
    function prescribes additional cardio sessions instead of further
    caloric restriction.

    Args:
        current_calories: Current daily caloric prescription (kcal).
        target_deficit: Desired daily caloric deficit (kcal, positive number).
        sex: ``"male"`` or ``"female"``.
        current_cardio_sessions: Weekly cardio sessions already prescribed.
        current_cardio_minutes: Total weekly cardio minutes.
        weeks_in_deficit: Weeks spent in current deficit phase.
        phase: Training phase (``"cut"``, ``"peak"``, etc.).

    Returns:
        Dict with prescription:
          - ``action``: ``"reduce_food"`` | ``"add_cardio"`` | ``"both"``
          - ``food_reduction_kcal``: how much to reduce from food (0 if cardio covers it)
          - ``cardio_sessions_to_add``: additional weekly sessions
          - ``cardio_minutes_to_add``: additional weekly minutes
          - ``cardio_modality``: recommended modality
          - ``rationale``: coaching explanation
    """
    sex_key = sex.strip().lower()
    intercept = _FLOOR_INTERCEPT.get(sex_key, 1800)

    # How much room is left before hitting the floor?
    room_to_cut = max(0, current_calories - intercept)

    # Max safe cardio (prevent overtraining): cap at 5 sessions / 200 min per week
    max_cardio_sessions = 5
    max_cardio_minutes = 200
    available_cardio_sessions = max(0, max_cardio_sessions - current_cardio_sessions)
    available_cardio_minutes = max(0, max_cardio_minutes - current_cardio_minutes)

    # Late prep modality selection
    if phase in ("peak", "cut") and weeks_in_deficit > 8:
        modality = "liss_incline_walk"
        burn_per_session = _CARDIO_BURN_ESTIMATES["liss_incline_walk"]
        modality_note = "LISS only (incline treadmill walk) — CNS is too fragile for HIIT"
    elif phase == "cut":
        modality = "liss_stairmaster"
        burn_per_session = _CARDIO_BURN_ESTIMATES["liss_stairmaster"]
        modality_note = "LISS (stairmaster) for pure fatty acid oxidation"
    else:
        modality = "zone2_cycling"
        burn_per_session = _CARDIO_BURN_ESTIMATES["zone2_cycling"]
        modality_note = "Zone 2 cycling for VO2max and insulin sensitivity"

    # Safety validation: ensure cardio prescription doesn't indirectly
    # push effective intake below the thermodynamic floor
    # Max cardio deficit = current calories - intercept (don't eat into the floor)
    max_safe_cardio_deficit = max(0, current_calories - intercept - food_cut if room_to_cut < target_deficit else target_deficit)

    # Decision logic
    if room_to_cut >= target_deficit:
        # Plenty of room — reduce food normally
        return {
            "action": "reduce_food",
            "food_reduction_kcal": round(target_deficit),
            "cardio_sessions_to_add": 0,
            "cardio_minutes_to_add": 0,
            "cardio_modality": None,
            "rationale": (
                f"Caloric intake ({current_calories:.0f} kcal) has sufficient room "
                f"above the {intercept} kcal floor. Reducing food by {target_deficit:.0f} kcal."
            ),
        }

    # Approaching the floor — use cardio to cover the gap
    food_cut = min(room_to_cut, target_deficit * 0.4)  # max 40% from food
    cardio_deficit_needed = min(target_deficit - food_cut, max_safe_cardio_deficit)

    sessions_needed = min(
        available_cardio_sessions,
        max(1, round(cardio_deficit_needed / burn_per_session)),
    )
    minutes_needed = min(available_cardio_minutes, sessions_needed * 30)
    actual_cardio_deficit = sessions_needed * burn_per_session

    if food_cut > 0:
        action = "both"
        rationale = (
            f"Caloric intake ({current_calories:.0f} kcal) is approaching the "
            f"{intercept} kcal floor. Splitting deficit: {food_cut:.0f} kcal from "
            f"food reduction + ~{actual_cardio_deficit:.0f} kcal from {sessions_needed} "
            f"additional cardio sessions. {modality_note}."
        )
    else:
        action = "add_cardio"
        rationale = (
            f"Caloric intake ({current_calories:.0f} kcal) is AT the {intercept} kcal "
            f"floor. Cannot reduce food further without metabolic damage. Adding "
            f"{sessions_needed} cardio sessions (~{actual_cardio_deficit:.0f} kcal/week). "
            f"{modality_note}."
        )

    return {
        "action": action,
        "food_reduction_kcal": round(food_cut),
        "cardio_sessions_to_add": sessions_needed,
        "cardio_minutes_to_add": minutes_needed,
        "cardio_modality": modality,
        "rationale": rationale,
    }


# ---------------------------------------------------------------------------
# 4.2  NEAT Tracking — Step Count Titration
# ---------------------------------------------------------------------------
# NEAT plummets as athletes get leaner and more lethargic.  This module
# prescribes escalating step targets and penalises missed targets by
# reducing carbs to balance unburned calories.

_STEP_TARGETS_BY_PHASE = {
    "bulk": 8000,
    "lean_bulk": 8000,
    "maintain": 8000,
    "restoration": 6000,
    "cut": 10000,       # first escalation
    "peak": 10000,      # maintain but don't increase (CNS fragile)
}

# Second escalation: when weight loss stalls during a cut
_STEP_TARGET_STALL = 12000

# Caloric estimate per 1000 steps (varies by bodyweight; ~30-50 kcal)
_KCAL_PER_1000_STEPS = 40.0


def compute_step_prescription(
    phase: str,
    weight_stall: bool = False,
    current_steps: int | None = None,
    weight_kg: float = 90.0,
) -> dict:
    """Prescribe daily step target based on training phase and stall status.

    Args:
        phase: Current training phase.
        weight_stall: True if weight loss has stalled (< 0.1 kg/week for 2+ weeks).
        current_steps: Yesterday's actual step count (for compliance check).
        weight_kg: Body weight for caloric estimate scaling.

    Returns:
        Dict with:
          - ``step_target``: prescribed daily steps
          - ``kcal_estimate``: estimated NEAT calories from hitting target
          - ``compliance``: True/False if current_steps provided
          - ``carb_penalty_g``: carbs to deduct if step target missed
          - ``note``: coaching guidance
    """
    phase_key = phase.strip().lower()
    base_target = _STEP_TARGETS_BY_PHASE.get(phase_key, 8000)

    # Escalate during stalls in cut phase
    if weight_stall and phase_key in ("cut", "peak"):
        step_target = _STEP_TARGET_STALL
        note = (
            f"Weight stall detected — step target escalated to {_STEP_TARGET_STALL:,} steps/day. "
            "Increasing NEAT before reducing calories further."
        )
    else:
        step_target = base_target
        note = f"Phase ({phase_key}): target {step_target:,} steps/day."

    # Scale caloric estimate by bodyweight (heavier athletes burn more per step)
    weight_factor = weight_kg / 80.0  # normalize to 80kg baseline
    kcal_per_1k = _KCAL_PER_1000_STEPS * weight_factor
    kcal_estimate = round((step_target / 1000) * kcal_per_1k)

    # Compliance check
    compliance = None
    carb_penalty = 0
    if current_steps is not None:
        compliance = current_steps >= step_target
        if not compliance:
            # Calculate unburned calories and convert to carb penalty
            missed_steps = step_target - current_steps
            missed_kcal = (missed_steps / 1000) * kcal_per_1k
            carb_penalty = round(missed_kcal / 4.0)  # 4 kcal/g carbs
            note += (
                f" Yesterday: {current_steps:,} steps (missed by {missed_steps:,}). "
                f"Deducting {carb_penalty}g carbs from today's allocation to balance."
            )
        else:
            note += f" Yesterday: {current_steps:,} steps — target met."

    return {
        "step_target": step_target,
        "kcal_estimate": kcal_estimate,
        "compliance": compliance,
        "carb_penalty_g": carb_penalty,
        "note": note,
    }


# ---------------------------------------------------------------------------
# 4.3  Active Cardio Periodization
# ---------------------------------------------------------------------------
# Cardio modality and frequency must be periodized based on training phase
# and recovery capacity (Engine 2 ARI).

# Phase-specific cardio prescriptions
_CARDIO_PRESCRIPTIONS: dict[str, dict] = {
    "bulk": {
        "sessions_per_week": 2,
        "duration_min": 20,
        "modality": "hiit",
        "modality_options": ["hiit_sprint", "hiit_cycling", "zone2_cycling"],
        "purpose": "Improve VO2max and insulin sensitivity without competing with surplus",
        "fasted": False,
        "notes": [
            "HIIT 2x/week or Zone 2 cycling — keeps cardiovascular health without burning surplus.",
            "Schedule on non-leg days to avoid interference with hypertrophy.",
            "Keep sessions short (15-20 min) to minimise caloric expenditure.",
        ],
    },
    "lean_bulk": {
        "sessions_per_week": 2,
        "duration_min": 25,
        "modality": "hiit",
        "modality_options": ["hiit_cycling", "zone2_cycling"],
        "purpose": "Partition nutrients toward muscle, limit fat gain",
        "fasted": False,
        "notes": [
            "Slightly longer sessions than full bulk to help partition calories.",
            "Zone 2 cycling preferred — minimal interference with leg recovery.",
        ],
    },
    "maintain": {
        "sessions_per_week": 3,
        "duration_min": 25,
        "modality": "mixed",
        "modality_options": ["zone2_cycling", "liss_incline_walk", "hiit_rowing"],
        "purpose": "Maintain cardiovascular fitness and metabolic flexibility",
        "fasted": False,
        "notes": [
            "Mix of HIIT and LISS for metabolic flexibility.",
            "3 sessions keeps the engine primed for future prep.",
        ],
    },
    "cut": {
        "sessions_per_week": 4,
        "duration_min": 30,
        "modality": "liss",
        "modality_options": ["liss_incline_walk", "liss_stairmaster", "liss_cycling"],
        "purpose": "Pure fatty acid oxidation — primary deficit driver alongside food reduction",
        "fasted": True,
        "notes": [
            "LISS only — pure fatty acid oxidation in the aerobic zone.",
            "Fasted AM cardio preferred (after coffee + EAAs for muscle protection).",
            "Increase duration before increasing frequency.",
            "HIIT is banned during cut — CNS is already taxed from deficit + heavy training.",
        ],
    },
    "peak": {
        "sessions_per_week": 3,
        "duration_min": 20,
        "modality": "liss",
        "modality_options": ["liss_incline_walk", "steady_state_elliptical"],
        "purpose": "Maintain caloric expenditure without glycogen depletion",
        "fasted": False,
        "notes": [
            "Reduce from cut-phase levels — glycogen must be preserved for carb load.",
            "Light LISS only (incline walk). No HIIT under any circumstances.",
            "Discontinue cardio 48h before show day to maximise fullness.",
        ],
    },
    "restoration": {
        "sessions_per_week": 2,
        "duration_min": 20,
        "modality": "liss",
        "modality_options": ["liss_incline_walk", "zone2_cycling"],
        "purpose": "Gentle reintroduction — let the body recover",
        "fasted": False,
        "notes": [
            "Minimal cardio during restoration — the body needs to rebuild.",
            "Light walks and Zone 2 only. No HIIT for at least 4 weeks post-show.",
        ],
    },
}


def compute_cardio_prescription(
    phase: str,
    weeks_in_phase: int = 0,
    avg_ari: float | None = None,
    weight_stall: bool = False,
    current_cardio_sessions: int = 0,
    days_since_last_leg_session: int | None = None,
) -> dict:
    """Generate a phase-appropriate cardio prescription.

    Integrates with Engine 2 ARI for recovery-aware adjustments:
    - ARI < 55: reduce cardio frequency by 1 session
    - ARI < 40: reduce to 1 session (minimum viable)

    Args:
        phase: Current training phase.
        weeks_in_phase: Weeks spent in current phase (for progressive overload).
        avg_ari: Average ARI from the last 7 days (Engine 2 cross-feed).
        weight_stall: True if weight loss has stalled for 2+ weeks.
        current_cardio_sessions: Current weekly sessions (for progressive adjustment).

    Returns:
        Dict with full cardio prescription.
    """
    phase_key = phase.strip().lower()
    base = _CARDIO_PRESCRIPTIONS.get(phase_key, _CARDIO_PRESCRIPTIONS["maintain"])

    sessions = base["sessions_per_week"]
    duration = base["duration_min"]
    modality = base["modality"]
    notes = list(base["notes"])

    # Progressive overload: increase duration after 4 weeks, sessions after 8
    if phase_key == "cut":
        if weeks_in_phase >= 8 and sessions < 5:
            sessions += 1
            notes.append(
                f"Week {weeks_in_phase}: adding 1 session (progressive cardio escalation)."
            )
        elif weeks_in_phase >= 4:
            duration = min(45, duration + 5)
            notes.append(
                f"Week {weeks_in_phase}: extending duration to {duration} min."
            )

    # Weight stall escalation
    if weight_stall and phase_key in ("cut", "peak"):
        if sessions < 5:
            sessions += 1
        duration = min(45, duration + 10)
        notes.append(
            "Weight stall detected — adding cardio volume before reducing food."
        )

    # ARI-aware recovery adjustment (Engine 2 → Engine 4 cross-feed)
    if avg_ari is not None:
        if avg_ari < 40:
            sessions = max(1, sessions - 2)
            notes.append(
                f"ARI CRITICAL ({avg_ari:.0f}): Cardio reduced to {sessions} session(s). "
                "Recovery is severely compromised — prioritise rest."
            )
        elif avg_ari < 55:
            sessions = max(1, sessions - 1)
            notes.append(
                f"ARI LOW ({avg_ari:.0f}): Reducing cardio by 1 session to protect recovery."
            )

    # Recovery-aware modality: avoid leg-intensive cardio within 48h of leg day
    # Zone 2 cycling taxes quads/calves — conflicts with Engine 2's 48h recovery window.
    # Incline treadmill walk is the safest option within 48h of leg training.
    modality_options = list(base["modality_options"])
    if days_since_last_leg_session is not None and days_since_last_leg_session < 2:
        if "zone2_cycling" in modality_options or "hiit_cycling" in modality_options:
            # Replace cycling with incline walk (leg-safe)
            modality_options = [
                m if m not in ("zone2_cycling", "hiit_cycling", "hiit_sprint")
                else "liss_incline_walk"
                for m in modality_options
            ]
            # Deduplicate while preserving order
            seen: set[str] = set()
            modality_options = [m for m in modality_options if not (m in seen or seen.add(m))]
            notes.append(
                f"Leg session {days_since_last_leg_session}d ago — switched to incline walk "
                "(cycling conflicts with 48h quad/calf recovery window)."
            )

    return {
        "sessions_per_week": sessions,
        "duration_min": duration,
        "modality": modality,
        "modality_options": modality_options,
        "fasted": base["fasted"],
        "purpose": base["purpose"],
        "weekly_time_commitment_min": sessions * duration,
        "estimated_weekly_burn_kcal": sessions * _CARDIO_BURN_ESTIMATES.get(
            modality_options[0] if modality_options else "liss_incline_walk", 200
        ),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# 4.4  Unified Expenditure Summary
# ---------------------------------------------------------------------------

def compute_total_expenditure_plan(
    phase: str,
    weight_kg: float,
    sex: str,
    current_calories: float,
    target_deficit: float = 0,
    weeks_in_phase: int = 0,
    avg_ari: float | None = None,
    weight_stall: bool = False,
    current_steps: int | None = None,
    current_cardio_sessions: int = 0,
    current_cardio_minutes: int = 0,
) -> dict:
    """Generate a unified expenditure plan combining cardio + NEAT + energy flux.

    This is the top-level Engine 4 function that orchestrates all three
    subroutines into a single coherent prescription.

    Returns:
        Dict with ``cardio``, ``neat``, ``energy_flux``, and ``summary`` keys.
    """
    cardio = compute_cardio_prescription(
        phase=phase,
        weeks_in_phase=weeks_in_phase,
        avg_ari=avg_ari,
        weight_stall=weight_stall,
        current_cardio_sessions=current_cardio_sessions,
    )

    neat = compute_step_prescription(
        phase=phase,
        weight_stall=weight_stall,
        current_steps=current_steps,
        weight_kg=weight_kg,
    )

    flux = compute_energy_flux_prescription(
        current_calories=current_calories,
        target_deficit=target_deficit,
        sex=sex,
        current_cardio_sessions=current_cardio_sessions + cardio["sessions_per_week"],
        current_cardio_minutes=current_cardio_minutes + cardio["weekly_time_commitment_min"],
        weeks_in_deficit=weeks_in_phase if phase in ("cut", "peak") else 0,
        phase=phase,
    )

    total_expenditure = (
        cardio["estimated_weekly_burn_kcal"]
        + (neat["kcal_estimate"] * 7)  # daily NEAT × 7
    )

    return {
        "cardio": cardio,
        "neat": neat,
        "energy_flux": flux,
        "summary": {
            "total_weekly_expenditure_kcal": round(total_expenditure),
            "cardio_weekly_kcal": cardio["estimated_weekly_burn_kcal"],
            "neat_weekly_kcal": neat["kcal_estimate"] * 7,
            "step_target": neat["step_target"],
            "cardio_sessions": cardio["sessions_per_week"],
            "cardio_duration_min": cardio["duration_min"],
            "food_reduction_needed_kcal": flux["food_reduction_kcal"],
            "phase": phase,
        },
    }
