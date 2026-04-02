#!/usr/bin/env python3
"""
End-to-end pipeline test: create user profile → run all 3 engines → generate program → verify.

Run inside the backend container:
    docker compose exec backend python scripts/e2e_pipeline_test.py
"""
import asyncio
import sys
import traceback
from datetime import date, timedelta

# Must be able to import the app
sys.path.insert(0, "/app")


async def main():
    from app.database import async_session
    from app.models.user import User
    from app.models.profile import UserProfile
    from app.models.training import Exercise
    from app.models.measurement import BodyWeightLog
    from sqlalchemy import select, func, text

    errors = []
    warnings = []

    def check(label, condition, msg=""):
        if not condition:
            errors.append(f"FAIL: {label} — {msg}")
            print(f"  FAIL: {label} — {msg}")
        else:
            print(f"  OK:   {label}")

    print("=" * 70)
    print("CORONADO E2E PIPELINE TEST")
    print("=" * 70)

    async with async_session() as db:
        # ─── 1. Verify exercise database ─────────────────────────────────
        print("\n[1] EXERCISE DATABASE")
        ex_count_result = await db.execute(select(func.count()).select_from(Exercise))
        ex_count = ex_count_result.scalar()
        check("Exercise count >= 185", ex_count >= 185, f"got {ex_count}")

        # Check delt sub-groups
        delt_result = await db.execute(
            select(Exercise.primary_muscle, func.count())
            .where(Exercise.primary_muscle.in_(["front_delt", "side_delt", "rear_delt"]))
            .group_by(Exercise.primary_muscle)
        )
        delt_counts = {row[0]: row[1] for row in delt_result.all()}
        check("front_delt exercises exist", delt_counts.get("front_delt", 0) > 0, str(delt_counts))
        check("side_delt exercises exist", delt_counts.get("side_delt", 0) > 0, str(delt_counts))
        check("rear_delt exercises exist", delt_counts.get("rear_delt", 0) > 0, str(delt_counts))

        # Check load_type populated
        lt_result = await db.execute(
            select(func.count()).select_from(Exercise).where(Exercise.load_type != None)
        )
        lt_count = lt_result.scalar()
        check("load_type populated", lt_count == ex_count, f"{lt_count}/{ex_count} have load_type")

        # ─── 2. Create test user ─────────────────────────────────────────
        print("\n[2] CREATE TEST USER")
        import uuid
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        test_email = f"e2e_test_{uuid.uuid4().hex[:8]}@test.com"
        test_user = User(
            email=test_email,
            username=f"e2e_test_{uuid.uuid4().hex[:6]}",
            hashed_password=pwd_context.hash("testpass123"),
            onboarding_complete=True,
        )
        db.add(test_user)
        await db.flush()
        user_id = test_user.id
        check("User created", user_id is not None, str(user_id))

        # ─── 3. Create profile (Men's Physique, intermediate) ────────────
        print("\n[3] CREATE PROFILE — Men's Physique, 188cm, intermediate")
        profile = UserProfile(
            user_id=user_id,
            sex="male",
            age=27,
            height_cm=188.0,
            division="mens_physique",
            training_experience_years=4,
            wrist_circumference_cm=17.5,
            ankle_circumference_cm=23.0,
            manual_body_fat_pct=14.0,
            days_per_week=5,
            training_start_time="06:00",
            training_duration_min=75,
            available_equipment=["barbell", "dumbbell", "cable", "machine", "bodyweight", "ez_bar", "smith_machine"],
            preferences={
                "preferred_split": "ppl",
                "meal_count": 5,
                "dietary_restrictions": [],
                "preferred_proteins": ["chicken", "egg", "whey"],
                "preferred_carbs": ["rice", "oats"],
                "preferred_fats": ["avocado", "olive oil"],
            },
        )
        db.add(profile)
        await db.flush()
        check("Profile created", profile.id is not None)

        # Add body weight
        bw = BodyWeightLog(user_id=user_id, weight_kg=88.5, recorded_date=date.today())
        db.add(bw)
        await db.flush()
        check("Body weight logged", True)

        # ─── 4. Run Engine 1 (Physique Diagnostics) ──────────────────────
        print("\n[4] ENGINE 1 — Physique Diagnostics")
        try:
            from app.engines.engine1.weight_cap import compute_weight_cap
            cap = compute_weight_cap(188.0, 17.5, 23.0, 14.0, "male")
            check("Weight cap computed", cap["stage_weight_kg"] > 0, f"stage={cap['stage_weight_kg']:.1f}kg")
            check("Offseason cap computed", cap["offseason_weight_kg"] > 0, f"off={cap['offseason_weight_kg']:.1f}kg")
            check("Max LBM computed", cap["max_lbm_kg"] > 0, f"lbm={cap['max_lbm_kg']:.1f}kg")
        except Exception as e:
            errors.append(f"FAIL: Engine 1 weight cap — {e}")
            print(f"  FAIL: Engine 1 weight cap — {e}")
            traceback.print_exc()

        try:
            from app.engines.engine1.weight_cap import compute_bf_threshold_from_weight_cap
            bf_eval = compute_bf_threshold_from_weight_cap(188.0, 88.5, 17.5, 23.0, "male", "mens_physique")
            check("BF threshold computed", "threshold_bf_pct" in bf_eval, str(bf_eval))
            check("Mini-cut evaluation", "should_mini_cut" in bf_eval, str(bf_eval))
        except Exception as e:
            errors.append(f"FAIL: Engine 1 BF threshold — {e}")
            print(f"  FAIL: Engine 1 BF threshold — {e}")
            traceback.print_exc()

        # ─── 5. Run Engine 2 (Training Program Generation) ───────────────
        print("\n[5] ENGINE 2 — Training Program Generation")
        try:
            from app.models.training import TrainingProgram, TrainingSession, TrainingSet
            from app.services.training import generate_program_sessions, DEFAULT_VOLUME

            program = TrainingProgram(
                user_id=user_id,
                name="E2E Test Program",
                split_type="ppl",
                days_per_week=5,
                mesocycle_weeks=6,
            )
            db.add(program)
            await db.flush()
            check("Program created", program.id is not None)

            sessions_created = await generate_program_sessions(
                db=db,
                user_id=user_id,
                program=program,
                volume_allocation=DEFAULT_VOLUME,
                start_date=date.today(),
            )
            check("Sessions generated", sessions_created > 0, f"{sessions_created} sessions")
            check("Sessions >= 25 (5d/wk × 6wk)", sessions_created >= 25, f"{sessions_created}")

            # Load first session to inspect
            sess_result = await db.execute(
                select(TrainingSession)
                .where(TrainingSession.program_id == program.id)
                .order_by(TrainingSession.session_date, TrainingSession.day_number)
                .limit(1)
            )
            first_session = sess_result.scalar_one_or_none()
            check("First session exists", first_session is not None)

            if first_session:
                check("dup_profile set", first_session.dup_profile is not None, f"dup={first_session.dup_profile}")

                sets_result = await db.execute(
                    select(TrainingSet, Exercise.name, Exercise.primary_muscle, Exercise.equipment,
                           Exercise.movement_pattern)
                    .join(Exercise, TrainingSet.exercise_id == Exercise.id)
                    .where(TrainingSet.session_id == first_session.id)
                    .order_by(TrainingSet.set_number)
                )
                sets = sets_result.all()
                check("Sets generated", len(sets) > 0, f"{len(sets)} sets")

                # Check rest_seconds populated
                working_sets = [s for s in sets if not s[0].is_warmup]
                warmup_sets = [s for s in sets if s[0].is_warmup]
                rest_populated = sum(1 for s in working_sets if s[0].rest_seconds is not None)
                check("rest_seconds on working sets", rest_populated == len(working_sets),
                      f"{rest_populated}/{len(working_sets)}")
                if warmup_sets:
                    wu_rest = sum(1 for s in warmup_sets if s[0].rest_seconds == 60)
                    check("warmup rest = 60s", wu_rest == len(warmup_sets),
                          f"{wu_rest}/{len(warmup_sets)}")

                # Check no banned exercises for MP
                banned_kws = {"deadlift", "barbell row", "t-bar row", "shrug", "barbell squat"}
                ex_names = [s[1].lower() for s in sets]
                for ban in banned_kws:
                    found = [n for n in ex_names if ban in n]
                    check(f"No '{ban}' in MP session", len(found) == 0,
                          f"BANNED exercise found: {found}")

                # Check side_delt exercises present somewhere in program
                all_sessions_result = await db.execute(
                    select(TrainingSet, Exercise.primary_muscle)
                    .join(Exercise, TrainingSet.exercise_id == Exercise.id)
                    .join(TrainingSession, TrainingSet.session_id == TrainingSession.id)
                    .where(TrainingSession.program_id == program.id)
                )
                all_muscles = {row[1] for row in all_sessions_result.all()}
                check("side_delt in program", "side_delt" in all_muscles, str(all_muscles))

                # Check FST-7 sets exist somewhere
                fst7_result = await db.execute(
                    select(func.count())
                    .select_from(TrainingSet)
                    .join(TrainingSession, TrainingSet.session_id == TrainingSession.id)
                    .where(TrainingSession.program_id == program.id, TrainingSet.is_fst7 == True)
                )
                fst7_count = fst7_result.scalar()
                check("FST-7 sets in program", fst7_count > 0, f"{fst7_count} FST-7 sets")

        except Exception as e:
            errors.append(f"FAIL: Engine 2 — {e}")
            print(f"  FAIL: Engine 2 — {e}")
            traceback.print_exc()

        # ─── 6. Run Engine 3 (Nutrition) ─────────────────────────────────
        print("\n[6] ENGINE 3 — Nutrition")
        try:
            from app.engines.engine3.macros import adjust_macros_for_phase
            offseason_macros = adjust_macros_for_phase(3000, 200, 350, 80, "maintain", "offseason")
            check("Offseason macros computed", offseason_macros["calories"] > 0, str(offseason_macros))
            check("Offseason surplus", offseason_macros["calories"] > 3000, f"{offseason_macros['calories']}")

            cut_macros = adjust_macros_for_phase(3000, 200, 350, 80, "offseason", "cut")
            check("Cut macros computed", cut_macros["calories"] > 0, str(cut_macros))
            check("Cut deficit", cut_macros["calories"] < 3000, f"{cut_macros['calories']}")
            check("Cut protein >= offseason", cut_macros["protein_g"] >= 200, f"{cut_macros['protein_g']}g")

            mini_cut_macros = adjust_macros_for_phase(3000, 200, 350, 80, "offseason", "mini_cut")
            check("Mini-cut deeper than cut", mini_cut_macros["calories"] <= cut_macros["calories"],
                  f"mini_cut={mini_cut_macros['calories']} vs cut={cut_macros['calories']}")
        except Exception as e:
            errors.append(f"FAIL: Engine 3 — {e}")
            print(f"  FAIL: Engine 3 — {e}")
            traceback.print_exc()

        # ─── 7. Cleanup test user ────────────────────────────────────────
        print("\n[7] CLEANUP")
        await db.execute(text("DELETE FROM training_sets WHERE session_id IN (SELECT id FROM training_sessions WHERE user_id = :uid)"), {"uid": str(user_id)})
        await db.execute(text("DELETE FROM training_sessions WHERE user_id = :uid"), {"uid": str(user_id)})
        await db.execute(text("DELETE FROM training_programs WHERE user_id = :uid"), {"uid": str(user_id)})
        await db.execute(text("DELETE FROM body_weight_log WHERE user_id = :uid"), {"uid": str(user_id)})
        await db.execute(text("DELETE FROM user_profiles WHERE user_id = :uid"), {"uid": str(user_id)})
        await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
        await db.commit()
        print("  OK:   Test user cleaned up")

    # ─── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    if errors:
        print(f"RESULT: {len(errors)} ERRORS")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("RESULT: ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
