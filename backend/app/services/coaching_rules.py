"""
Coaching Feedback Engine — rule-based expert system (no LLM).

Each rule returns a structured CoachingMessage dict or None. Messages are
written in the voice of a direct, experienced coach: specific thresholds,
specific actions, no hedging.

Severity levels:
  - info:    observation, no action required
  - warning: trend needs attention within the next 1-2 weeks
  - action:  do something THIS week

The dispatcher (generate_coaching_feedback) runs every rule against the
user's recent data and returns the combined non-null outputs.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any


# ---------------------------------------------------------------------------
# Typed message
# ---------------------------------------------------------------------------

@dataclass
class CoachingMessage:
    severity: str           # info | warning | action
    category: str           # weight | hrv | adherence | plateau | deload | volume | pattern
    title: str
    body: str
    metric_value: float | None = None
    threshold: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Weight rate (cutting + bulking guardrails)  — FU-13
# ---------------------------------------------------------------------------

def check_weight_rate(
    weights_14d: list[tuple[date, float]],
    phase: str,
) -> CoachingMessage | None:
    """
    Flag too-fast / too-slow weight change.

    weights_14d: sorted ascending (oldest first) list of (date, kg).
    phase: "cut" | "peak" | "lean_bulk" | "bulk" | "maintain" | "restoration"
    """
    if len(weights_14d) < 7:
        return None

    vals = [w for _, w in weights_14d]
    # 7-day simple moving averages at start and end of window
    early_sma = statistics.mean(vals[:7])
    late_sma = statistics.mean(vals[-7:])
    days_between = (weights_14d[-1][0] - weights_14d[0][0]).days or 1
    weekly_delta = (late_sma - early_sma) * 7 / days_between
    pct = weekly_delta / late_sma * 100 if late_sma > 0 else 0

    phase_l = (phase or "").lower()
    if phase_l in ("cut", "peak"):
        if pct < -1.5:
            return CoachingMessage(
                severity="action",
                category="weight",
                title="Weight loss rate too aggressive",
                body=(
                    f"You're down {abs(pct):.1f}% body weight per week. Above 1.5% is where "
                    "LBM loss accelerates. Add a refeed day this week — eat at maintenance "
                    "on your heaviest training day. If the rate doesn't settle into 0.5-1.0% "
                    "next week, bump baseline calories by 150 kcal."
                ),
                metric_value=round(pct, 2),
                threshold=-1.5,
            )
        if -0.3 <= pct <= 0 and len(weights_14d) >= 14:
            return CoachingMessage(
                severity="warning",
                category="weight",
                title="Weight loss has plateaued",
                body=(
                    f"Only {abs(pct):.2f}% loss per week over the last two weeks. Pick one: "
                    "drop ~200 kcal from baseline OR add a 4th weekly cardio session. "
                    "Don't stack both — change one variable at a time."
                ),
                metric_value=round(pct, 2),
                threshold=-0.3,
            )
    elif phase_l in ("lean_bulk", "bulk"):
        if pct > 0.5:
            return CoachingMessage(
                severity="action",
                category="weight",
                title="Gaining too fast",
                body=(
                    f"You're up {pct:.2f}% per week — above 0.5% means most of the gain is fat, "
                    "not muscle. Pull your surplus back by 150 kcal (drop ~40g carbs). Target "
                    "rate is 0.2-0.4% per week for lean tissue preferentially."
                ),
                metric_value=round(pct, 2),
                threshold=0.5,
            )
        if 0 <= pct < 0.15 and phase_l == "bulk":
            return CoachingMessage(
                severity="warning",
                category="weight",
                title="Surplus is too small to build mass",
                body=(
                    f"Only {pct:.2f}% gain per week. For a traditional bulk you want 0.25-0.5%. "
                    "Add 200 kcal (50g carbs) and re-check in 10 days."
                ),
                metric_value=round(pct, 2),
                threshold=0.15,
            )
    return None


# ---------------------------------------------------------------------------
# HRV trend
# ---------------------------------------------------------------------------

def check_hrv_trend(hrv_14d: list[tuple[date, float]]) -> CoachingMessage | None:
    """
    Flag a sustained HRV drop of >=10% from the early-week baseline to the
    late-week average. Caller provides sorted-ascending (date, rmssd_or_sdnn).
    """
    if len(hrv_14d) < 7:
        return None
    vals = [v for _, v in hrv_14d]
    early = statistics.mean(vals[: len(vals) // 2])
    late = statistics.mean(vals[len(vals) // 2 :])
    if early <= 0:
        return None
    drop_pct = (early - late) / early * 100
    if drop_pct >= 10:
        return CoachingMessage(
            severity="warning",
            category="hrv",
            title="HRV trending down",
            body=(
                f"Your morning HRV average is down {drop_pct:.0f}% from a week ago. "
                "Systemic fatigue is accumulating. Cut 1 set per exercise on your next "
                "two sessions, sleep ≥8h, and keep HIIT cardio off the menu this week."
            ),
            metric_value=round(drop_pct, 1),
            threshold=10.0,
        )
    return None


# ---------------------------------------------------------------------------
# Adherence drop
# ---------------------------------------------------------------------------

def check_adherence_drop(
    sessions_completed: int, sessions_planned: int
) -> CoachingMessage | None:
    if sessions_planned < 3:
        return None
    pct = (sessions_completed / sessions_planned) * 100
    if pct < 70:
        return CoachingMessage(
            severity="action",
            category="adherence",
            title="Training adherence dropped",
            body=(
                f"Only {sessions_completed}/{sessions_planned} sessions done this week "
                f"({pct:.0f}%). Consistency matters more than intensity. Look at your "
                "schedule — is a specific day the problem? You can reorder the split in "
                "Settings so the missed day becomes your rest day."
            ),
            metric_value=round(pct, 1),
            threshold=70.0,
        )
    return None


# ---------------------------------------------------------------------------
# Plateau detection  — FU-10
# ---------------------------------------------------------------------------

def _epley_1rm(weight: float, reps: int) -> float:
    return weight * (1 + reps / 30) if reps > 0 else 0


def _brzycki_1rm(weight: float, reps: int) -> float:
    if reps <= 0 or reps >= 37:
        return weight
    return weight * 36 / (37 - reps)


def check_plateau(
    exercise_name: str,
    last_four_sessions: list[dict],
) -> CoachingMessage | None:
    """
    last_four_sessions: list of dicts {weight_kg, reps} — the athlete's top
    working set per session for this exercise, oldest first.

    Flag when estimated 1RM changes < 1% across 3 consecutive sessions.
    """
    if len(last_four_sessions) < 3:
        return None
    e1rms = []
    for s in last_four_sessions:
        w = s.get("weight_kg") or 0
        r = s.get("reps") or 0
        if w <= 0 or r <= 0:
            continue
        e1rms.append((_epley_1rm(w, r) + _brzycki_1rm(w, r)) / 2)
    if len(e1rms) < 3:
        return None

    # Look at the last 3 e1RMs
    recent = e1rms[-3:]
    baseline = recent[0]
    if baseline <= 0:
        return None
    pct_changes = [abs(v - baseline) / baseline for v in recent[1:]]
    if all(pc < 0.01 for pc in pct_changes):
        return CoachingMessage(
            severity="warning",
            category="plateau",
            title=f"{exercise_name} has plateaued",
            body=(
                f"{exercise_name} has sat at ~{recent[-1]:.0f} kg e1RM for 3 sessions. "
                "Pick one variation: change the rep range, swap to a close variation "
                "(flat→incline, barbell→dumbbell), or add a rest-pause set on your top "
                "working set next session."
            ),
            metric_value=round(recent[-1], 1),
            threshold=1.0,
            meta={"exercise": exercise_name},
        )
    return None


# ---------------------------------------------------------------------------
# Deload trigger  — FU-11
# ---------------------------------------------------------------------------

def check_deload_needed(
    ari_scores_7d: list[float],
    weeks_since_deload: int,
    declining_exercises_2w: int = 0,
) -> CoachingMessage | None:
    """
    Trigger a deload when ANY of:
      - ARI composite <50 for 3+ consecutive days
      - 3+ exercises declined for 2 consecutive sessions
      - 6+ weeks since last deload (safety cap)
    """
    triggered = False
    reasons: list[str] = []

    # Consecutive low-ARI days
    low_streak = 0
    max_low_streak = 0
    for v in ari_scores_7d:
        if v < 50:
            low_streak += 1
            max_low_streak = max(max_low_streak, low_streak)
        else:
            low_streak = 0
    if max_low_streak >= 3:
        triggered = True
        reasons.append(f"ARI <50 for {max_low_streak} consecutive days")

    if declining_exercises_2w >= 3:
        triggered = True
        reasons.append(f"{declining_exercises_2w} exercises regressing for 2 weeks")

    if weeks_since_deload >= 6:
        triggered = True
        reasons.append(f"{weeks_since_deload} weeks since last deload")

    if not triggered:
        return None
    return CoachingMessage(
        severity="action",
        category="deload",
        title="Take a deload week",
        body=(
            "Recovery indicators are flagging: "
            + "; ".join(reasons)
            + ". Drop working volume to ~50% (halve the sets) but keep the loads and "
            "movement patterns the same. One week. Then re-ramp."
        ),
        metric_value=float(max_low_streak),
        threshold=3.0,
        meta={"reasons": reasons},
    )


# ---------------------------------------------------------------------------
# Volume vs landmarks
# ---------------------------------------------------------------------------

def check_volume_vs_landmarks(
    current_volume: dict[str, int],
    landmarks: dict[str, dict[str, int]],
) -> list[CoachingMessage]:
    """
    Surface any muscles where current weekly volume is BELOW_MEV or ABOVE_MRV.
    Returns a list (can surface multiple muscles at once).
    """
    messages: list[CoachingMessage] = []
    below_mev = []
    above_mrv = []
    for muscle, sets in current_volume.items():
        lm = landmarks.get(muscle)
        if not lm:
            continue
        if sets < lm["mev"] and sets > 0:
            below_mev.append((muscle, sets, lm["mev"]))
        elif sets > lm["mrv"]:
            above_mrv.append((muscle, sets, lm["mrv"]))

    if below_mev:
        muscle_list = ", ".join(
            f"{m.replace('_', ' ')} ({s}/{mev})" for m, s, mev in below_mev
        )
        messages.append(CoachingMessage(
            severity="warning",
            category="volume",
            title=f"{len(below_mev)} muscle{'s' if len(below_mev) != 1 else ''} below MEV",
            body=(
                f"These muscles aren't getting enough stimulus to grow: {muscle_list}. "
                "Add 2-3 sets each. If your split is already tight, superset them with "
                "a non-competing muscle."
            ),
            meta={"muscles": [m for m, _, _ in below_mev]},
        ))

    if above_mrv:
        muscle_list = ", ".join(
            f"{m.replace('_', ' ')} ({s}/{mrv})" for m, s, mrv in above_mrv
        )
        messages.append(CoachingMessage(
            severity="action",
            category="volume",
            title=f"{len(above_mrv)} muscle{'s' if len(above_mrv) != 1 else ''} above MRV",
            body=(
                f"You're past recovery capacity on: {muscle_list}. Volume above MRV just "
                "accumulates fatigue without stimulus. Cut 3-4 sets per muscle this week."
            ),
            meta={"muscles": [m for m, _, _ in above_mrv]},
        ))

    return messages


# ---------------------------------------------------------------------------
# Adherence pattern detection  — FU-15 / B9
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def check_adherence_patterns(sessions_history: list[dict]) -> CoachingMessage | None:
    """
    sessions_history: list of {session_date (date | iso str), completed: bool}
    covering the last 8 weeks. Flag a weekday that has been missed 3+ times.
    """
    if len(sessions_history) < 10:
        return None
    miss_days: list[int] = []
    for s in sessions_history:
        if s.get("completed"):
            continue
        d = s.get("session_date")
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                continue
        if not d:
            continue
        miss_days.append(d.weekday())
    counts = Counter(miss_days)
    if not counts:
        return None
    worst_dow, worst_count = counts.most_common(1)[0]
    if worst_count >= 3:
        name = _WEEKDAY_NAMES[worst_dow]
        return CoachingMessage(
            severity="info",
            category="pattern",
            title=f"{name} is your bottleneck day",
            body=(
                f"You've missed {worst_count} {name} sessions in the last 8 weeks. "
                "Consider moving this session to a day you're more consistent with — "
                "adherence > optimal split."
            ),
            metric_value=float(worst_count),
            threshold=3.0,
            meta={"weekday": name, "count": worst_count},
        )
    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def generate_coaching_feedback(
    user_id,
    db,
) -> list[dict]:
    """
    Run every rule against the user's recent data. Returns the combined
    non-null rule outputs as a list of message dicts.
    """
    from sqlalchemy import select, desc
    from app.models.measurement import BodyWeightLog
    from app.models.training import HRVLog, ARILog, TrainingSession, StrengthLog, Exercise
    from app.models.profile import UserProfile
    from app.models.nutrition import NutritionPrescription
    from app.engines.engine2.volume_landmarks import get_all_landmarks

    today = date.today()
    fortnight_ago = today - timedelta(days=14)
    eight_weeks_ago = today - timedelta(days=56)

    msgs: list[CoachingMessage] = []

    # Weight (14d)
    bw_rows = (await db.execute(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == user_id, BodyWeightLog.recorded_date >= fortnight_ago)
        .order_by(BodyWeightLog.recorded_date)
    )).scalars().all()
    weights = [(r.recorded_date, r.weight_kg) for r in bw_rows]

    rx = (await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user_id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )).scalar_one_or_none()
    phase = rx.phase if rx else "maintain"

    m = check_weight_rate(weights, phase)
    if m:
        msgs.append(m)

    # HRV (14d)
    hrv_rows = (await db.execute(
        select(HRVLog)
        .where(HRVLog.user_id == user_id, HRVLog.recorded_date >= fortnight_ago)
        .order_by(HRVLog.recorded_date)
    )).scalars().all()
    hrv_pts = [(r.recorded_date, r.rmssd) for r in hrv_rows if r.rmssd is not None]
    m = check_hrv_trend(hrv_pts)
    if m:
        msgs.append(m)

    # Adherence (this week)
    week_start = today - timedelta(days=today.weekday())
    sessions_this_week = (await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.user_id == user_id,
            TrainingSession.session_date >= week_start,
            TrainingSession.session_date <= today,
        )
    )).scalars().all()
    planned = len(sessions_this_week)
    completed = sum(1 for s in sessions_this_week if s.completed)
    m = check_adherence_drop(completed, planned)
    if m:
        msgs.append(m)

    # Adherence patterns (8w)
    sessions_8w = (await db.execute(
        select(TrainingSession)
        .where(
            TrainingSession.user_id == user_id,
            TrainingSession.session_date >= eight_weeks_ago,
            TrainingSession.session_date < week_start,
        )
    )).scalars().all()
    pattern_history = [
        {"session_date": s.session_date, "completed": s.completed}
        for s in sessions_8w
    ]
    m = check_adherence_patterns(pattern_history)
    if m:
        msgs.append(m)

    # Plateau — look at last 4 sessions for top working set per exercise
    # (only check the 6 most-logged exercises to bound cost)
    strength_rows = (await db.execute(
        select(StrengthLog, Exercise)
        .join(Exercise, StrengthLog.exercise_id == Exercise.id)
        .where(StrengthLog.user_id == user_id)
        .order_by(desc(StrengthLog.recorded_date))
        .limit(40)
    )).all()
    by_ex: dict[str, list[dict]] = {}
    for sl, ex in strength_rows:
        by_ex.setdefault(ex.name, []).append({
            "weight_kg": sl.weight_kg, "reps": sl.reps,
        })
    for name, sessions in list(by_ex.items())[:6]:
        if len(sessions) >= 3:
            # Oldest-first
            oldest_first = list(reversed(sessions[:4]))
            m = check_plateau(name, oldest_first)
            if m:
                msgs.append(m)
                break  # one plateau message per check-in; avoid noise

    # Deload trigger
    ari_rows = (await db.execute(
        select(ARILog)
        .where(
            ARILog.user_id == user_id,
            ARILog.recorded_date >= today - timedelta(days=7),
        )
        .order_by(ARILog.recorded_date)
    )).scalars().all()
    ari_scores = [r.ari_score for r in ari_rows if r.ari_score is not None]
    # Best-effort: weeks-since-deload from the training program's current_week
    weeks_since_deload = 0
    from app.models.training import TrainingProgram
    prog = (await db.execute(
        select(TrainingProgram)
        .where(TrainingProgram.user_id == user_id, TrainingProgram.is_active == True)
        .order_by(desc(TrainingProgram.created_at)).limit(1)
    )).scalar_one_or_none()
    if prog:
        # If mesocycle is 6-week MEV→MRV→deload, the last week is the deload.
        # weeks_since_deload = current_week if mesocycle_weeks >= 6 else current_week - (peak+1)
        weeks_since_deload = max(0, (prog.current_week or 1) - 1)

    m = check_deload_needed(ari_scores, weeks_since_deload)
    if m:
        msgs.append(m)

    # Volume vs landmarks
    profile = (await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )).scalar_one_or_none()
    training_years = getattr(profile, "training_experience_years", None) if profile else None
    landmarks = get_all_landmarks(training_years)

    # Week's set counts per muscle
    from sqlalchemy import and_
    from app.models.training import TrainingSet
    count_rows = (await db.execute(
        select(Exercise.primary_muscle)
        .join(TrainingSet, TrainingSet.exercise_id == Exercise.id)
        .join(TrainingSession, TrainingSession.id == TrainingSet.session_id)
        .where(
            and_(
                TrainingSession.user_id == user_id,
                TrainingSession.session_date >= week_start,
                TrainingSession.session_date <= today,
                TrainingSet.is_warmup == False,
            )
        )
    )).all()
    weekly_volume: dict[str, int] = {}
    for (muscle,) in count_rows:
        if muscle:
            weekly_volume[muscle] = weekly_volume.get(muscle, 0) + 1
    for msg in check_volume_vs_landmarks(weekly_volume, landmarks):
        msgs.append(msg)

    return [m.to_dict() for m in msgs]
