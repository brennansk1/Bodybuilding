"""
Division-specific mandatory poses and posing practice recommendations.

Each division has a set of mandatory poses that athletes must practice.
Practice frequency and duration scale with proximity to competition.
"""
from __future__ import annotations

from typing import Optional

# Mandatory poses by division — these are the poses judged on stage
DIVISION_POSES: dict[str, list[dict[str, str]]] = {
    "mens_open": [
        {"name": "Front Double Biceps", "cue": "Flare lats, squeeze biceps, vacuum waist"},
        {"name": "Front Lat Spread", "cue": "Push lats wide, chest up, quad separation"},
        {"name": "Side Chest", "cue": "Crush arm across, expand chest, flex calf"},
        {"name": "Back Double Biceps", "cue": "Spread lats, squeeze biceps, flex hamstrings"},
        {"name": "Back Lat Spread", "cue": "Maximum lat width, glute-ham tie-in visible"},
        {"name": "Side Triceps", "cue": "Lock arm straight, push tricep, flex obliques"},
        {"name": "Abdominals & Thigh", "cue": "Crunch abs, hands behind head, quad feathering"},
        {"name": "Most Muscular", "cue": "Crab or hands-on-hips — maximum density"},
    ],
    "classic_physique": [
        {"name": "Front Double Biceps", "cue": "Classic vacuum, arms at ~90 degrees"},
        {"name": "Front Lat Spread", "cue": "Wide lats, tight waist, quad sweep"},
        {"name": "Side Chest", "cue": "Crush arm, Arnold-style chest expansion"},
        {"name": "Back Double Biceps", "cue": "Spread lats, squeeze biceps, glute-ham detail"},
        {"name": "Back Lat Spread", "cue": "Lat width with tight waist, calf flex"},
        {"name": "Abdominals & Thigh", "cue": "Vacuum pose, quad separation"},
        {"name": "Favorite Classic Pose", "cue": "Choose your signature — vacuum, victory, etc."},
    ],
    "mens_physique": [
        {"name": "Front Relaxed", "cue": "Shoulders back, lats slightly flared, confident smile"},
        {"name": "Back Relaxed", "cue": "V-taper visible, lats spread subtly, calves popped"},
        {"name": "Left Quarter Turn", "cue": "Show shoulder cap, arm relaxed, torso twisted slightly"},
        {"name": "Right Quarter Turn", "cue": "Mirror left side, consistent arm position"},
        {"name": "Model Walk", "cue": "Confident stride, shoulders open, personality showing"},
    ],
    "womens_figure": [
        {"name": "Front Pose", "cue": "One leg forward, shoulders back, slight twist"},
        {"name": "Back Pose", "cue": "Show back width, glute-ham detail, calf separation"},
        {"name": "Left Side", "cue": "Front leg bent, show shoulder cap and quad sweep"},
        {"name": "Right Side", "cue": "Mirror left, show X-frame from opposite angle"},
        {"name": "Model Walk", "cue": "T-walk with smooth transitions, confident posture"},
    ],
    "womens_bikini": [
        {"name": "Front Pose", "cue": "One foot forward, slight hip tilt, shoulders back"},
        {"name": "Back Pose", "cue": "Glute presentation, slight hip pop, relaxed upper body"},
        {"name": "Left Side", "cue": "Show shoulder-to-waist ratio, glute shape"},
        {"name": "Right Side", "cue": "Mirror left, even presentation"},
        {"name": "Model Walk", "cue": "T-walk with personality, confident smile, hip sway"},
        {"name": "Front Transition", "cue": "Smooth front-to-back pivot, maintain posture"},
    ],
    "womens_physique": [
        {"name": "Front Double Biceps", "cue": "Show muscle detail with femininity"},
        {"name": "Front Lat Spread", "cue": "Lat width, tight waist, quad definition"},
        {"name": "Side Chest", "cue": "Chest expansion, arm detail, calf flex"},
        {"name": "Back Double Biceps", "cue": "Back detail, glute-ham, calf symmetry"},
        {"name": "Back Lat Spread", "cue": "Maximum width, lower back detail"},
        {"name": "Side Triceps", "cue": "Tricep separation, oblique control"},
        {"name": "Abdominals & Thigh", "cue": "Core detail, quad feathering"},
    ],
    "wellness": [
        {"name": "Front Pose", "cue": "Shoulder-to-hip ratio, quad sweep visible"},
        {"name": "Back Pose", "cue": "Glute fullness is key — hamstring tie-in, V-taper"},
        {"name": "Left Side", "cue": "Show glute size, shoulder cap, waist tightness"},
        {"name": "Right Side", "cue": "Mirror left, even glute presentation"},
        {"name": "Model Walk", "cue": "T-walk emphasizing lower body, confident transitions"},
        {"name": "Front Transition", "cue": "Smooth pivot showing full physique"},
    ],
}


def get_posing_recommendation(
    division: str,
    weeks_out: Optional[int],
) -> dict:
    """Return posing practice recommendations based on proximity to competition.

    Coach-aligned scaling:
    - 16+ weeks out: 2x/week, 10 min sessions — learn the poses
    - 12-16 weeks out: 3x/week, 15 min — refine transitions
    - 8-12 weeks out: 4x/week, 20 min — practice under fatigue
    - 4-8 weeks out: 5x/week, 25 min — daily-ish, hold poses longer
    - <4 weeks out: Daily, 30+ min — full routine run-throughs
    - Peak week: 2x/day, 15 min each — morning + evening practice
    """
    poses = DIVISION_POSES.get(division, DIVISION_POSES.get("mens_open", []))

    if weeks_out is None or weeks_out > 16:
        frequency = "2x per week"
        duration_min = 10
        hold_seconds = 5
        intensity = "learning"
        notes = "Focus on learning each pose. Use a mirror. Don't worry about conditioning yet."
    elif weeks_out > 12:
        frequency = "3x per week"
        duration_min = 15
        hold_seconds = 7
        intensity = "refining"
        notes = "Practice transitions between poses. Start holding each pose for 7 seconds."
    elif weeks_out > 8:
        frequency = "4x per week"
        duration_min = 20
        hold_seconds = 10
        intensity = "building_endurance"
        notes = "Practice posing after training (under fatigue). Hold each pose 10 seconds. This mimics stage conditions."
    elif weeks_out > 4:
        frequency = "5x per week"
        duration_min = 25
        hold_seconds = 15
        intensity = "competition_prep"
        notes = "Run through your full mandatory routine. Hold each pose 15 seconds. Practice your walk-on and transitions."
    elif weeks_out > 1:
        frequency = "Daily"
        duration_min = 30
        hold_seconds = 20
        intensity = "peak_practice"
        notes = "Full routine daily. Hold each pose 20 seconds minimum. Practice in posing trunks/suit and competition shoes."
    else:
        frequency = "2x daily (AM + PM)"
        duration_min = 15
        hold_seconds = 15
        intensity = "peak_week"
        notes = "Short focused sessions. Morning: full routine. Evening: problem poses only. Stay hydrated. Don't overtax muscles."

    return {
        "division": division,
        "weeks_out": weeks_out,
        "frequency": frequency,
        "duration_min": duration_min,
        "hold_seconds": hold_seconds,
        "intensity": intensity,
        "notes": notes,
        "poses": poses,
    }
