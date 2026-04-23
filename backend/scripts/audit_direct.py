#!/usr/bin/env python3
"""
Direct DB audit — bypasses auth, reads all data for a user, runs engines directly.
Usage: docker compose exec backend python audit_direct.py [username]
"""
import asyncio
import json
import sys
from datetime import date

from sqlalchemy import select, desc
from app.database import async_session
from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import TapeMeasurement, SkinfoldMeasurement, BodyWeightLog
from app.models.diagnostic import PDSLog, HQILog, LCSALog
from app.models.training import (
    TrainingProgram, TrainingSession, Exercise, StrengthBaseline, StrengthLog
)
from app.models.nutrition import NutritionPrescription


def pp(label, data):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    if data is None:
        print("  (none)")
        return
    if hasattr(data, '__dict__'):
        for k, v in sorted(vars(data).items()):
            if k.startswith('_'):
                continue
            print(f"  {k}: {v}")
    elif isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"  {data}")


async def audit(username: str):
    async with async_session() as db:
        # ── User ──
        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if not user:
            print(f"User '{username}' not found")
            return
        uid = user.id
        print(f"\nUser: {user.username} ({user.email}) | ID: {uid}")
        print(f"Onboarding complete: {user.onboarding_complete}")

        # ── Profile ──
        profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == uid))).scalar_one_or_none()
        pp("PROFILE", profile)

        # ── Latest Weight ──
        w = (await db.execute(
            select(BodyWeightLog).where(BodyWeightLog.user_id == uid).order_by(desc(BodyWeightLog.recorded_date)).limit(5)
        )).scalars().all()
        if w:
            pp("RECENT WEIGHTS", [{"date": str(x.recorded_date), "kg": x.weight_kg} for x in w])
        else:
            pp("RECENT WEIGHTS", None)

        # ── Latest Tape ──
        tape = (await db.execute(
            select(TapeMeasurement).where(TapeMeasurement.user_id == uid).order_by(desc(TapeMeasurement.recorded_date)).limit(1)
        )).scalar_one_or_none()
        if tape:
            tape_dict = {}
            for col in ['neck', 'shoulders', 'chest', 'left_bicep', 'right_bicep',
                        'left_forearm', 'right_forearm', 'waist', 'hips',
                        'left_thigh', 'right_thigh', 'left_calf', 'right_calf',
                        'chest_relaxed', 'chest_lat_spread', 'back_width',
                        'left_proximal_thigh', 'right_proximal_thigh',
                        'left_distal_thigh', 'right_distal_thigh']:
                v = getattr(tape, col, None)
                if v is not None:
                    tape_dict[col] = v
            pp(f"TAPE MEASUREMENTS ({tape.recorded_date})", tape_dict)
        else:
            pp("TAPE MEASUREMENTS", None)

        # ── Latest Skinfolds ──
        sf = (await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == uid).order_by(desc(SkinfoldMeasurement.recorded_date)).limit(1)
        )).scalar_one_or_none()
        if sf:
            sf_dict = {}
            for col in ['chest', 'midaxillary', 'tricep', 'subscapular', 'abdominal',
                        'suprailiac', 'thigh', 'bicep', 'lower_back', 'calf', 'body_fat_pct']:
                v = getattr(sf, col, None)
                if v is not None:
                    sf_dict[col] = v
            pp(f"SKINFOLDS ({sf.recorded_date})", sf_dict)
        else:
            pp("SKINFOLDS", None)

        # ── Run Engine 1 ──
        print("\n" + "="*70)
        print("  RUNNING ENGINE 1 DIAGNOSTICS...")
        print("="*70)
        bf = wc = gm = ce = pt = am = None
        try:
            from app.services.diagnostic import run_full_diagnostic
            diag = await run_full_diagnostic(db, user)

            bf = diag.get("body_fat")
            pp("BODY FAT ANALYSIS", bf)

            wc = diag.get("weight_cap")
            pp("WEIGHT CAP (Casey Butt)", wc)

            gm = diag.get("ghost_model")
            pp("VOLUMETRIC GHOST MODEL", gm)

            ce = diag.get("class_estimate")
            pp("CLASS ESTIMATE", ce)

            pt = diag.get("prep_timeline")
            pp("PREP TIMELINE", pt)

            am = diag.get("advanced_measurements")
            pp("ADVANCED MEASUREMENTS", am)
        except Exception as e:
            print(f"  Engine 1 error: {e}")
            import traceback
            traceback.print_exc()

        # ── PDS ──
        pds = (await db.execute(
            select(PDSLog).where(PDSLog.user_id == uid).order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1)
        )).scalar_one_or_none()
        if pds:
            pp("PDS SCORE", {
                "date": str(pds.recorded_date),
                "score": pds.pds_score,
                "tier": pds.tier,
                "components": pds.component_scores,
            })
        else:
            pp("PDS SCORE", None)

        # ── HQI ──
        hqi = (await db.execute(
            select(HQILog).where(HQILog.user_id == uid).order_by(desc(HQILog.recorded_date)).limit(1)
        )).scalar_one_or_none()
        if hqi:
            pp("HQI (Hypertrophy Quality Index)", {
                "date": str(hqi.recorded_date),
                "overall": hqi.overall_hqi,
                "sites": hqi.site_scores,
            })
        else:
            pp("HQI", None)

        # ── LCSA ──
        lcsa = (await db.execute(
            select(LCSALog).where(LCSALog.user_id == uid).order_by(desc(LCSALog.recorded_date)).limit(1)
        )).scalar_one_or_none()
        if lcsa:
            pp("LCSA (Lean Cross-Sectional Area)", {
                "date": str(lcsa.recorded_date),
                "total": lcsa.total_lcsa,
                "sites": lcsa.site_values,
            })
        else:
            pp("LCSA", None)

        # ── Nutrition Prescription ──
        rx = (await db.execute(
            select(NutritionPrescription).where(
                NutritionPrescription.user_id == uid,
                NutritionPrescription.is_active == True
            ).limit(1)
        )).scalar_one_or_none()
        if rx:
            pp("NUTRITION PRESCRIPTION", {
                "phase": rx.phase,
                "tdee": rx.tdee,
                "target_calories": rx.target_calories,
                "protein_g": rx.protein_g,
                "carbs_g": rx.carbs_g,
                "fat_g": rx.fat_g,
                "peri_workout_carb_pct": rx.peri_workout_carb_pct,
            })
        else:
            pp("NUTRITION PRESCRIPTION", None)

        # ── Now compute what a coach would prescribe ──
        if profile and w:
            print("\n" + "="*70)
            print("  PRO BODYBUILDER CROSS-CHECK")
            print("="*70)

            bw = w[0].weight_kg
            height_cm = profile.height_cm
            division = profile.division
            sex = profile.sex
            age = profile.age
            exp_years = profile.training_experience_years or 0
            bf_pct = sf.body_fat_pct if sf else (profile.manual_body_fat_pct or None)
            lbm = bw * (1 - bf_pct/100) if bf_pct else None

            print(f"\n  Athlete: {sex}, {age}y, {height_cm}cm, {bw}kg, {division}")
            print(f"  BF%: {bf_pct}%, LBM: {lbm:.1f}kg" if bf_pct and lbm else f"  BF%: unknown")
            print(f"  Experience: {exp_years} years")

            # ── Coach-level checks ──
            print(f"\n  --- Protein Check ---")
            if rx and lbm:
                prot_per_kg = rx.protein_g / bw
                prot_per_kg_lbm = rx.protein_g / lbm
                print(f"  Prescribed: {rx.protein_g}g = {prot_per_kg:.2f} g/kg BW = {prot_per_kg_lbm:.2f} g/kg LBM")

                # Literature range
                if rx.phase in ("cut", "peak_week"):
                    ideal_range = (2.2, 2.7)
                elif rx.phase in ("bulk", "lean_bulk"):
                    ideal_range = (1.8, 2.2)
                else:
                    ideal_range = (1.8, 2.4)

                status = "OK" if ideal_range[0] <= prot_per_kg <= ideal_range[1] else "REVIEW"
                print(f"  Literature range for {rx.phase}: {ideal_range[0]}-{ideal_range[1]} g/kg BW")
                print(f"  Status: {status}")

            print(f"\n  --- Fat Floor Check ---")
            if rx and lbm:
                fat_per_kg = rx.fat_g / bw
                print(f"  Prescribed: {rx.fat_g}g = {fat_per_kg:.2f} g/kg BW")
                min_fat = 0.4 if rx.phase == "peak_week" else 0.7
                status = "OK" if fat_per_kg >= min_fat else "TOO LOW — hormonal risk"
                print(f"  Minimum for {rx.phase}: {min_fat} g/kg")
                print(f"  Status: {status}")

            print(f"\n  --- Calorie Check ---")
            if rx and lbm:
                # Katch-McArdle
                bmr_km = 370 + 21.6 * lbm
                tdee_est = bmr_km * 1.55  # moderate activity
                print(f"  Katch-McArdle BMR: {bmr_km:.0f} kcal")
                print(f"  Estimated TDEE (×1.55): {tdee_est:.0f} kcal")
                print(f"  Engine TDEE: {rx.tdee:.0f} kcal")
                print(f"  Target cals: {rx.target_calories:.0f} kcal")
                diff = rx.target_calories - tdee_est
                print(f"  Surplus/Deficit vs estimate: {diff:+.0f} kcal")

            print(f"\n  --- Weight Cap Check ---")
            if wc:
                cap = wc.get("weight_cap_kg")
                stage = wc.get("stage_weight_kg")
                target_lbm = wc.get("target_lbm_kg")
                print(f"  Weight cap: {cap}kg, Stage weight: {stage}kg, Target LBM: {target_lbm}kg")
                if lbm and target_lbm:
                    gap_kg = target_lbm - lbm
                    print(f"  Current LBM: {lbm:.1f}kg, Gap to target: {gap_kg:+.1f}kg")
                    if gap_kg <= 0:
                        print(f"  AT or ABOVE target LBM — ready for cutting phase")
                    else:
                        # Estimate time at 0.2kg muscle/month
                        months = gap_kg / 0.2
                        print(f"  ~{months:.0f} months of bulking needed (0.2kg muscle/mo)")

            print(f"\n  --- Body Fat Method Check ---")
            if bf:
                source = bf.get("source", "unknown")
                confidence = bf.get("confidence", "unknown")
                methods = bf.get("methods", [])
                print(f"  Source: {source}, Confidence: {confidence}")
                print(f"  Methods used: {methods}")
                if bf.get("confidence_interval"):
                    lo, hi = bf["confidence_interval"]
                    print(f"  CI: [{lo:.1f}%, {hi:.1f}%] (spread: {hi-lo:.1f}%)")


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "samplesk"
    asyncio.run(audit(username))
