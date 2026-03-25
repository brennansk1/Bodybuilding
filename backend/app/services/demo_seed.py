"""
Demo admin account seed.

Creates a fully-populated Men's Open competitor (Marcus Reyes) for hands-on
testing of every dashboard, chart, and algorithm without going through onboarding.

Credentials
-----------
  email    : admin@coronado.dev
  password : coronado2024

Run automatically on startup (idempotent — skipped if user already exists).
"""
import logging
import uuid
from datetime import date, timedelta

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import BodyWeightLog, TapeMeasurement, SkinfoldMeasurement
from app.models.training import (
    StrengthBaseline, HRVLog, ARILog,
    TrainingProgram, TrainingSession, TrainingSet, Exercise,
)
from app.models.diagnostic import LCSALog, PDSLog, HQILog
from app.models.nutrition import NutritionPrescription, AdherenceLog, WeeklyCheckin

logger = logging.getLogger(__name__)
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_EMAIL = "admin@coronado.dev"
DEMO_PASSWORD = "admin123"
DEMO_USERNAME = "marcus_demo"

# Today
TODAY = date(2026, 3, 18)


def _d(weeks_ago: int, day_offset: int = 0) -> date:
    return TODAY - timedelta(weeks=weeks_ago) + timedelta(days=day_offset)


# ---------------------------------------------------------------------------
# Athlete profile constants
# ---------------------------------------------------------------------------
# Marcus Reyes — 28yo / 182cm / Men's Open / 7 yrs training
# Currently 16 weeks out from competition — deep cut phase
# Started cut 12 weeks ago at 105.2kg / 16.2% BF
# Current:  98.8kg / 11.6% BF — PDS 78 / tier: advanced

# 12-week weight trajectory (weekly weigh-in)
WEIGHT_HISTORY = [
    (_d(12), 105.2), (_d(11), 104.5), (_d(10), 103.8), (_d(9), 103.2),
    (_d(8),  102.7), (_d(7),  102.1), (_d(6),  101.5), (_d(5),  101.0),
    (_d(4),  100.4), (_d(3),   99.8), (_d(2),   99.3), (_d(1),   98.8),
    (TODAY,   98.5),
]

# Tape measurements at weeks 12, 8, 4, 0 (current) — slight improvements
TAPE_SNAPSHOTS = [
    {   # 12 weeks ago — start of cut
        "date": _d(12),
        "neck": 40.5, "shoulders": 130.0, "chest": 120.5,
        "left_bicep": 44.5, "right_bicep": 45.0,
        "left_forearm": 35.5, "right_forearm": 36.0,
        "waist": 86.0, "hips": 101.5,
        "left_thigh": 63.5, "right_thigh": 64.0,
        "left_calf": 41.5, "right_calf": 42.0,
    },
    {   # 8 weeks ago — waist tightening, arms holding
        "date": _d(8),
        "neck": 40.5, "shoulders": 130.5, "chest": 120.0,
        "left_bicep": 44.5, "right_bicep": 45.0,
        "left_forearm": 35.5, "right_forearm": 36.0,
        "waist": 83.5, "hips": 100.0,
        "left_thigh": 63.5, "right_thigh": 64.0,
        "left_calf": 41.5, "right_calf": 42.0,
    },
    {   # 4 weeks ago — significant waist drop
        "date": _d(4),
        "neck": 40.5, "shoulders": 130.5, "chest": 120.0,
        "left_bicep": 45.0, "right_bicep": 45.5,
        "left_forearm": 36.0, "right_forearm": 36.5,
        "waist": 81.5, "hips": 99.0,
        "left_thigh": 64.0, "right_thigh": 64.5,
        "left_calf": 42.0, "right_calf": 42.5,
    },
    {   # Current — peaked look, tight waist
        "date": TODAY,
        "neck": 41.0, "shoulders": 131.0, "chest": 120.5,
        "left_bicep": 45.0, "right_bicep": 45.5,
        "left_forearm": 36.0, "right_forearm": 36.5,
        "waist": 80.0, "hips": 98.5,
        "left_thigh": 64.0, "right_thigh": 64.5,
        "left_calf": 42.0, "right_calf": 42.5,
        # Advanced sites for heatmap granularity
        "chest_relaxed": 114.5, "chest_lat_spread": 122.0, "back_width": 54.5,
        "left_proximal_thigh": 68.5, "right_proximal_thigh": 69.2,
        "left_distal_thigh": 53.5, "right_distal_thigh": 54.2,
    },
]

# 7-site Jackson-Pollock skinfolds (mm) at same snapshots
SKINFOLD_SNAPSHOTS = [
    (_d(12), dict(chest=12.0, midaxillary=14.0, tricep=14.5, subscapular=16.0,
                  abdominal=22.0, suprailiac=18.0, thigh=18.0, body_fat_pct=16.2)),
    (_d(8),  dict(chest=10.5, midaxillary=12.5, tricep=13.0, subscapular=14.5,
                  abdominal=19.5, suprailiac=16.0, thigh=16.0, body_fat_pct=14.3)),
    (_d(4),  dict(chest=9.0,  midaxillary=11.0, tricep=11.5, subscapular=13.0,
                  abdominal=17.0, suprailiac=14.0, thigh=14.5, body_fat_pct=12.6)),
    (TODAY,  dict(chest=7.5,  midaxillary=9.5,  tricep=10.0, subscapular=11.5,
                  abdominal=15.0, suprailiac=12.0, thigh=13.0, body_fat_pct=11.6)),
]

# PDS/HQI/LCSA progression over 4 check-ins (weeks 12, 8, 4, 0)
PDS_HISTORY = [
    (_d(12), 62.4, {"muscle_mass": 74.0, "conditioning": 51.0, "symmetry": 88.0, "overall_hqi": 68.0}, "intermediate"),
    (_d(8),  68.1, {"muscle_mass": 75.0, "conditioning": 62.0, "symmetry": 89.0, "overall_hqi": 70.0}, "advanced"),
    (_d(4),  73.5, {"muscle_mass": 76.0, "conditioning": 72.0, "symmetry": 89.0, "overall_hqi": 72.0}, "advanced"),
    (TODAY,  78.2, {"muscle_mass": 77.0, "conditioning": 80.0, "symmetry": 90.0, "overall_hqi": 73.5}, "advanced"),
]

HQI_HISTORY = [
    (_d(12), {
        "neck": 72.0, "shoulders": 85.0, "chest": 80.0, "bicep": 76.0,
        "forearm": 52.0, "waist": 65.0, "hips": 74.0, "thigh": 79.0, "calf": 45.0,
    }, 69.8),
    (_d(8), {
        "neck": 73.0, "shoulders": 86.0, "chest": 81.0, "bicep": 77.0,
        "forearm": 53.0, "waist": 68.0, "hips": 75.0, "thigh": 80.0, "calf": 46.0,
    }, 71.0),
    (_d(4), {
        "neck": 74.0, "shoulders": 87.0, "chest": 82.0, "bicep": 78.0,
        "forearm": 54.0, "waist": 71.0, "hips": 76.0, "thigh": 81.0, "calf": 47.0,
    }, 72.2),
    (TODAY, {
        "neck": 75.0, "shoulders": 88.0, "chest": 83.0, "bicep": 79.0,
        "forearm": 55.0, "waist": 74.0, "hips": 77.0, "thigh": 82.0, "calf": 48.0,
    }, 73.5),
]

LCSA_HISTORY = [
    (_d(12), {
        "neck": 31.2, "chest": 89.1, "bicep": 36.9, "forearm": 30.8,
        "waist": 62.4, "hips": 80.2, "thigh": 54.7, "calf": 35.3,
    }, 421.0),
    (_d(8),  {
        "neck": 31.3, "chest": 89.5, "bicep": 37.1, "forearm": 30.9,
        "waist": 63.8, "hips": 80.5, "thigh": 55.0, "calf": 35.5,
    }, 423.5),
    (_d(4),  {
        "neck": 31.5, "chest": 89.8, "bicep": 37.4, "forearm": 31.2,
        "waist": 65.2, "hips": 81.0, "thigh": 55.4, "calf": 35.8,
    }, 427.3),
    (TODAY,  {
        "neck": 31.8, "chest": 90.2, "bicep": 37.8, "forearm": 31.5,
        "waist": 67.1, "hips": 81.5, "thigh": 55.8, "calf": 36.0,
    }, 431.7),
]

# HRV data for 28 days — realistic variation showing good recovery baseline
HRV_DATA = []
for i in range(28):
    d = TODAY - timedelta(days=27 - i)
    import math
    # RMSSD oscillates 58-78 with weekly pattern (lower mid-week from training)
    base_rmssd = 68 + 8 * math.sin(i * 2 * math.pi / 7 + 1.0)
    rmssd = round(base_rmssd + (i % 3 - 1) * 2, 1)
    rhr = round(54 - 0.05 * i + (i % 4 - 2) * 0.5, 1)
    sleep = round(min(9.5, 7.5 + 0.3 * math.sin(i * 2 * math.pi / 7)), 1)
    soreness = round(max(1.0, 4.5 - 0.5 * math.sin(i * 2 * math.pi / 7 + 3)), 1)
    HRV_DATA.append((d, rmssd, rhr, sleep, soreness))

# ARI from the HRV data (approximated)
ARI_DATA = []
for d, rmssd, rhr, sleep, soreness in HRV_DATA:
    # ARI approximation: high RMSSD + low RHR + high sleep + low soreness = high ARI
    ari = min(100.0, max(0.0, (rmssd - 40) / 40 * 40 + (10 - soreness) / 9 * 30 + sleep / 10 * 30))
    ARI_DATA.append((d, round(ari, 1), rmssd, sleep, soreness))


# ---------------------------------------------------------------------------
# Training exercises lookup keys (by name fragment + muscle group)
# We look these up at seed time rather than hardcoding UUIDs.
# ---------------------------------------------------------------------------

EXERCISE_LOOKUPS = {
    # (name_fragment, muscle_group): variable_name
    "chest_bench":    ("Barbell Bench Press - Medium Grip", "chest"),
    "chest_decline":  ("Decline barbell bench press", "chest"),
    "chest_cgbp":     ("Close-grip bench press", "chest"),
    "back_row":       ("Single-arm barbell bent-over row", "back"),
    "back_pullover":  ("Bent-arm barbell pull-over", "back"),
    "shoulders_mil":  ("Military press", "shoulders"),
    "quads_squat":    ("Barbell Full Squat", "quads"),
    "quads_legpress": ("Barbell back squat to box", "quads"),
    "hams_dl":        ("Barbell Deadlift", "hamstrings"),
    "biceps_curl":    ("Barbell Curl", "biceps"),
    "biceps_wide":    ("Wide-grip barbell curl", "biceps"),
    "triceps_skull":  ("Incline EZ-bar skullcrusher", "triceps"),
    "triceps_cgbp":   ("Close-grip bench press", "chest"),  # also used as triceps
    "glutes_thrust":  ("Barbell Hip Thrust", "glutes"),
}


# ---------------------------------------------------------------------------
# Session schedule: PPL split — 4 days/week for 4 weeks
# Week 1-3 = historical (3 weeks back to 1 week back); week 4 = current
# ---------------------------------------------------------------------------

def _session_schedule(program_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    """
    4-week mesocycle, 4 sessions/week: Push/Pull/Legs/Upper
    Mon=Push, Tue=Pull, Thu=Legs, Fri=Upper

    Anchored so week 4 starts on the most recent Monday, ensuring today falls
    within the current week and at least one upcoming session exists.
    """
    sessions = []
    # Find Monday of the current ISO week
    days_since_monday = TODAY.weekday()  # Mon=0 … Sun=6
    this_monday = TODAY - timedelta(days=days_since_monday)

    # 6-week mesocycle: current_week=4, so week 1 started 3 weeks ago
    # 5 days/week: Mon, Tue, Wed, Fri, Sat (matches _WEEKLY_SCHEDULE[5])
    session_day_offsets = [0, 1, 2, 4, 5]
    session_types = [
        "quads_priority", "back_rear_delts", "chest_side_delts",
        "hams_glutes", "upper_pump_fst7",
    ]

    for week_num in range(1, 7):  # 6-week mesocycle
        week_monday = this_monday - timedelta(weeks=(4 - week_num))
        for day_num, (day_offset, stype) in enumerate(
            zip(session_day_offsets, session_types), start=1
        ):
            session_date = week_monday + timedelta(days=day_offset)
            is_past = session_date < TODAY
            sessions.append({
                "id": uuid.uuid4(),
                "program_id": program_id,
                "user_id": user_id,
                "session_date": session_date,
                "session_type": stype,
                "week_number": week_num,
                "day_number": day_num,
                "completed": is_past,
                "split_type": "custom",
            })
    return sessions


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

async def seed_demo_admin(db: AsyncSession) -> bool:
    """
    Seed the demo admin account. Returns True if created, False if already exists.
    Idempotent — safe to call every startup.
    """
    existing = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    if existing.scalar_one_or_none():
        return False  # already seeded

    logger.info("Seeding demo admin account (admin@coronado.dev)…")

    # ------------------------------------------------------------------
    # 1. User
    # ------------------------------------------------------------------
    user = User(
        email=DEMO_EMAIL,
        username=DEMO_USERNAME,
        hashed_password=_pwd.hash(DEMO_PASSWORD),
        onboarding_complete=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # ------------------------------------------------------------------
    # 2. Profile
    # ------------------------------------------------------------------
    profile = UserProfile(
        user_id=user.id,
        sex="male",
        age=28,
        height_cm=182.0,
        division="mens_open",
        competition_date=date(2026, 7, 4),
        training_experience_years=7,
        wrist_circumference_cm=17.5,
        ankle_circumference_cm=22.5,
        preferences={
            "training_days_per_week": 4,
            "preferred_split": "ppl",
            "meal_count": 5,
            "units": "metric",
            "display_name": "Marcus",
            "cardio_machine": "stairmaster",
            "notifications": {"training": True, "nutrition": True, "checkin": True},
        },
    )
    db.add(profile)
    await db.flush()

    # ------------------------------------------------------------------
    # 3. Body weight log (13 data points over 12 weeks)
    # ------------------------------------------------------------------
    for d, weight in WEIGHT_HISTORY:
        db.add(BodyWeightLog(user_id=user.id, weight_kg=weight, recorded_date=d))

    # ------------------------------------------------------------------
    # 4. Tape measurements (4 snapshots)
    # ------------------------------------------------------------------
    for snap in TAPE_SNAPSHOTS:
        d = snap.pop("date")
        db.add(TapeMeasurement(user_id=user.id, recorded_date=d, **snap))
        snap["date"] = d  # restore

    # ------------------------------------------------------------------
    # 5. Skinfold measurements (4 snapshots)
    # ------------------------------------------------------------------
    for d, fields in SKINFOLD_SNAPSHOTS:
        db.add(SkinfoldMeasurement(user_id=user.id, recorded_date=d, **fields))

    # ------------------------------------------------------------------
    # 6. Diagnostic logs (LCSA / HQI / PDS) — 4 check-in points
    # ------------------------------------------------------------------
    for (d, sites, total), (_, hqi_sites, overall_hqi), (_, pds, components, tier) in zip(
        LCSA_HISTORY, HQI_HISTORY, PDS_HISTORY
    ):
        db.add(LCSALog(
            user_id=user.id, recorded_date=d,
            site_values=sites, total_lcsa=total,
        ))
        db.add(HQILog(
            user_id=user.id, recorded_date=d,
            site_scores=hqi_sites, overall_hqi=overall_hqi,
        ))
        db.add(PDSLog(
            user_id=user.id, recorded_date=d,
            pds_score=pds, component_scores=components, tier=tier,
        ))

    # ------------------------------------------------------------------
    # 7. Strength baselines — 6 key lifts
    # ------------------------------------------------------------------
    # Look up exercises by name
    ex_map: dict[str, uuid.UUID] = {}
    lookups = [
        ("bench", "Barbell Bench Press - Medium Grip"),
        ("squat", "Barbell Full Squat"),
        ("deadlift", "Barbell Deadlift"),
        ("row", "Single-arm barbell bent-over row"),
        ("ohp", "Military press"),
        ("curl", "Barbell Curl"),
    ]
    for key, name in lookups:
        r = await db.execute(select(Exercise).where(Exercise.name == name).limit(1))
        ex = r.scalar_one_or_none()
        if ex:
            ex_map[key] = ex.id

    baseline_data = {
        "bench":    (140.0, _d(12)),
        "squat":    (180.0, _d(12)),
        "deadlift": (220.0, _d(12)),
        "row":      (100.0, _d(12)),
        "ohp":      (90.0,  _d(12)),
        "curl":     (65.0,  _d(12)),
    }
    for key, (one_rm, d) in baseline_data.items():
        if key in ex_map:
            db.add(StrengthBaseline(
                user_id=user.id, exercise_id=ex_map[key],
                one_rm_kg=one_rm, recorded_date=d,
            ))

    # ------------------------------------------------------------------
    # 8. HRV + ARI logs (28 days)
    # ------------------------------------------------------------------
    for d, rmssd, rhr, sleep, soreness in HRV_DATA:
        db.add(HRVLog(
            user_id=user.id, recorded_date=d,
            rmssd=rmssd, resting_hr=rhr,
            sleep_quality=sleep, soreness_score=soreness,
        ))
    for d, ari, rmssd, sleep, soreness in ARI_DATA:
        hrv_comp = min(100.0, (rmssd - 40) / 40 * 100)
        sleep_comp = sleep / 10 * 100
        soreness_comp = (10 - soreness) / 9 * 100
        db.add(ARILog(
            user_id=user.id, recorded_date=d, ari_score=ari,
            hrv_component=round(hrv_comp, 1),
            sleep_component=round(sleep_comp, 1),
            soreness_component=round(soreness_comp, 1),
        ))

    # ------------------------------------------------------------------
    # 9. Training program + sessions + sets
    # ------------------------------------------------------------------
    program = TrainingProgram(
        user_id=user.id,
        name="Coronado 16-Week Contest Prep — Mesocycle 3",
        split_type="custom",
        days_per_week=5,
        mesocycle_weeks=6,
        current_week=3,
        is_active=True,
        volume_allocation={
            "chest": 14, "back": 18, "shoulders": 12, "quads": 16,
            "hamstrings": 12, "glutes": 8, "biceps": 10, "triceps": 10,
            "calves": 10, "abs": 6,
        },
        custom_template=[
            {"day": "Day 1 (Quads Priority)", "muscles": ["quads", "calves", "abs"]},
            {"day": "Day 2 (Back & Rear Delts)", "muscles": ["back", "rear_delt", "biceps"]},
            {"day": "Day 3 (Chest & Side Delts)", "muscles": ["chest", "side_delt", "triceps"]},
            {"day": "Day 4 (Hams & Glutes)", "muscles": ["hamstrings", "glutes", "calves"]},
            {"day": "Day 5 (Shoulders & Arms)", "muscles": ["shoulders", "biceps", "triceps"]}
        ]
    )
    db.add(program)
    await db.flush()

    session_defs = _session_schedule(program.id, user.id)

    # Collect exercises per session type for set generation
    push_exs = await _get_exercises(db, ["chest", "shoulders", "triceps"], limit=2)
    pull_exs = await _get_exercises(db, ["back", "biceps"], limit=2)
    legs_exs = await _get_exercises(db, ["quads", "hamstrings", "glutes"], limit=2)
    upper_exs = await _get_exercises(db, ["chest", "back", "shoulders", "biceps", "triceps"], limit=1)

    session_exercise_map = {
        "push": push_exs,
        "pull": pull_exs,
        "legs": legs_exs,
        "upper_body": upper_exs,
    }

    # Base weights per exercise slot — increases each week (progressive overload)
    base_weights = {
        "chest":      [110.0, 80.0],
        "shoulders":  [70.0,  50.0],
        "triceps":    [60.0,  50.0],
        "back":       [85.0,  70.0],
        "biceps":     [50.0,  40.0],
        "quads":      [160.0, 130.0],
        "hamstrings": [100.0, 80.0],
        "glutes":     [120.0, 90.0],
    }

    for sess_def in session_defs:
        week = sess_def["week_number"]
        stype = sess_def["session_type"]
        exs = session_exercise_map.get(stype, [])

        session = TrainingSession(
            id=sess_def["id"],
            program_id=program.id,
            user_id=user.id,
            session_date=sess_def["session_date"],
            session_type=stype,
            week_number=week,
            day_number=sess_def["day_number"],
            completed=sess_def["completed"],
            split_type="custom",
            stale_baselines=False,
            notes=(
                f"Week {week} — felt strong today, pumps were great."
                if sess_def["completed"] else None
            ),
        )
        db.add(session)
        await db.flush()

        if not sess_def["completed"]:
            # Only create prescribed sets for upcoming sessions
            _add_prescribed_sets(db, session.id, exs, week, base_weights)
        else:
            # Completed sessions: add both prescribed and actual logged weights
            _add_completed_sets(db, session.id, exs, week, base_weights)

    # ------------------------------------------------------------------
    # 10. Nutrition prescription (active cut protocol)
    # ------------------------------------------------------------------
    db.add(NutritionPrescription(
        user_id=user.id,
        tdee=3150.0,
        target_calories=2650.0,     # ~500 kcal deficit
        protein_g=225.0,            # 2.3g/kg bodyweight (contest prep)
        carbs_g=270.0,
        fat_g=70.0,
        peri_workout_carb_pct=0.40,
        phase="cut",
        is_active=True,
    ))

    # ------------------------------------------------------------------
    # 11. Adherence logs (4 weeks of adherence history)
    # ------------------------------------------------------------------
    adherence_data = [
        (_d(4), 91.0, 100.0, 95.5),
        (_d(3), 88.0, 100.0, 94.0),
        (_d(2), 93.0,  75.0, 84.0),  # missed a session week 2
        (_d(1), 95.0, 100.0, 97.5),
    ]
    for d, nut, train, overall in adherence_data:
        db.add(AdherenceLog(
            user_id=user.id, recorded_date=d,
            nutrition_adherence_pct=nut,
            training_adherence_pct=train,
            overall_adherence_pct=overall,
        ))

    # ------------------------------------------------------------------
    # 12. Weekly check-ins (4 processed check-ins)
    # ------------------------------------------------------------------
    checkin_data = [
        (_d(12), 1, 105.2, 68.5, 56.0, 7.5, 4.5, 88.0, 100.0, 62.4, 71.2),
        (_d(8),  5, 102.7, 70.2, 54.5, 7.8, 4.0, 91.0, 100.0, 68.1, 74.8),
        (_d(4),  9, 100.4, 72.1, 54.0, 8.1, 3.5, 88.0,  75.0, 73.5, 72.5),
        (_d(1), 12,  98.8, 71.8, 53.5, 8.3, 3.2, 93.0, 100.0, 78.2, 78.9),
    ]
    for (d, wk, bw, rmssd, rhr, sleep, soreness,
         nut_adh, trn_adh, pds, ari) in checkin_data:
        db.add(WeeklyCheckin(
            user_id=user.id, week_number=wk, checkin_date=d,
            body_weight_kg=bw, avg_rmssd=rmssd, avg_resting_hr=rhr,
            avg_sleep_quality=sleep, soreness_score=soreness,
            nutrition_adherence_pct=nut_adh, training_adherence_pct=trn_adh,
            pds_score=pds, ari_score=ari, processed=True,
        ))

    await db.flush()
    logger.info(
        f"Demo admin seeded — email: {DEMO_EMAIL} | "
        f"password: {DEMO_PASSWORD} | PDS: 78.2 (advanced)"
    )
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OLYMPIC_TERMS = [
    "clean", "snatch", "jerk", "power clean", "hang clean", "power snatch",
    "blocks", "complex", "thruster",
]

_PREFERRED_EXERCISES = {
    # muscle_group: [(name_fragment, exact=True/False), ...]
    "chest":      [("Barbell Bench Press - Medium Grip", True), ("Incline Dumbbell Press", True),
                   ("Dumbbell Flyes", True), ("Cable Crossover", False)],
    "back":       [("Bent Over Barbell Row", True), ("Single-arm barbell bent-over row", True),
                   ("Lat Pulldown", True), ("Seated Cable Row", False)],
    "shoulders":  [("Dumbbell Lateral Raise", True), ("Seated Dumbbell Palms-In Alternate Front Raise", False),
                   ("Barbell Shoulder Press", False), ("Machine Shoulder Press", False)],
    "quads":      [("Barbell Full Squat", True), ("Leg Press", False),
                   ("Hack Squat", False), ("Leg Extensions", False)],
    "hamstrings": [("Romanian Deadlift", False), ("Lying Leg Curls", False),
                   ("Seated Leg Curl", False), ("Stiff-Legged Deadlift", False)],
    "glutes":     [("Barbell Hip Thrust", True), ("Barbell glute bridge", True),
                   ("Kneeling Squat", True), ("Barbell Walking Lunge", False)],
    "biceps":     [("Barbell Curl", True), ("Dumbbell Alternate Bicep Curl", False),
                   ("Preacher Curl", True), ("Hammer Curls", False)],
    "triceps":    [("Triceps Pushdown - Rope Attachment", False), ("Skull Crusher", False),
                   ("Tricep Dumbbell Kickback", False), ("Close-grip bench press", True)],
    "calves":     [("Standing Calf Raises", False), ("Seated Calf Raise", False)],
    "abs":        [("Cable Crunches", False), ("Crunches", False)],
}


async def _get_exercises(
    db: AsyncSession, muscles: list[str], limit: int = 2
) -> list[tuple[uuid.UUID, str]]:
    """
    Return (exercise_id, primary_muscle) tuples for the given muscle groups.
    Prefers standard bodybuilding movements over Olympic lifts.
    """
    from sqlalchemy import or_, func as sqlfunc

    results = []
    for muscle in muscles:
        found: list[tuple[uuid.UUID, str]] = []

        # 1. Try preferred exercise name list first
        for name_hint, exact in _PREFERRED_EXERCISES.get(muscle, []):
            if len(found) >= limit:
                break
            if exact:
                r = await db.execute(
                    select(Exercise)
                    .where(Exercise.name == name_hint, Exercise.user_id.is_(None))
                    .limit(1)
                )
            else:
                r = await db.execute(
                    select(Exercise)
                    .where(
                        Exercise.name.ilike(f"%{name_hint}%"),
                        Exercise.primary_muscle == muscle,
                        Exercise.user_id.is_(None),
                    )
                    .limit(1)
                )
            ex = r.scalar_one_or_none()
            if ex:
                found.append((ex.id, muscle))

        # 2. Fill remaining slots from DB, excluding Olympic lifts
        if len(found) < limit:
            exclude_conditions = [
                Exercise.name.ilike(f"%{term}%") for term in _OLYMPIC_TERMS
            ]
            r = await db.execute(
                select(Exercise)
                .where(
                    Exercise.primary_muscle == muscle,
                    Exercise.user_id.is_(None),
                    *[~cond for cond in exclude_conditions],
                    Exercise.equipment.in_(["barbell", "dumbbell", "cable", "machine"]),
                )
                .order_by(Exercise.biomechanical_efficiency.desc())
                .limit(limit - len(found))
            )
            for ex in r.scalars():
                if (ex.id, muscle) not in found:
                    found.append((ex.id, muscle))

        results.extend(found[:limit])
    return results


def _add_prescribed_sets(
    db: AsyncSession,
    session_id: uuid.UUID,
    exercises: list[tuple[uuid.UUID, str]],
    week: int,
    base_weights: dict,
) -> None:
    """Add prescribed-only sets (upcoming session)."""
    weight_mult = 1.0 + (week - 1) * 0.02  # +2% per week
    for ex_id, muscle in exercises:
        base = base_weights.get(muscle, [60.0, 50.0])
        w = round(base[0] * weight_mult, 1)
        for set_num in range(1, 5):
            db.add(TrainingSet(
                session_id=session_id, exercise_id=ex_id,
                set_number=set_num, prescribed_reps=10,
                prescribed_weight_kg=w, is_warmup=(set_num == 1),
            ))


def _add_completed_sets(
    db: AsyncSession,
    session_id: uuid.UUID,
    exercises: list[tuple[uuid.UUID, str]],
    week: int,
    base_weights: dict,
) -> None:
    """Add completed sets with actual weights and RPE."""
    import random
    weight_mult = 1.0 + (week - 1) * 0.02
    for ex_id, muscle in exercises:
        base = base_weights.get(muscle, [60.0, 50.0])
        w = round(base[0] * weight_mult, 1)
        for set_num in range(1, 5):
            actual_w = w if set_num > 1 else w * 0.60  # warmup at 60%
            actual_reps = 10 if set_num > 1 else 15
            rpe = 6.0 if set_num == 1 else round(7.0 + (set_num - 2) * 0.5, 1)
            db.add(TrainingSet(
                session_id=session_id, exercise_id=ex_id,
                set_number=set_num, prescribed_reps=10,
                prescribed_weight_kg=w,
                actual_reps=actual_reps,
                actual_weight_kg=actual_w,
                rpe=rpe,
                is_warmup=(set_num == 1),
            ))
