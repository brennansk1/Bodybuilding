import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.profile import UserProfile
from app.models.nutrition import NutritionPrescription
from app.models.training import TrainingProgram, StrengthBaseline

async def audit():
    async with async_session() as db:
        stmt = select(User).order_by(User.created_at.desc()).limit(1)
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            print("No users found")
            return
            
        print(f"User: {user.username} ({user.email})")
        
        # Profile
        stmt = select(UserProfile).where(UserProfile.user_id == user.id)
        profile = (await db.execute(stmt)).scalars().first()
        if profile:
            print("\n--- Profile ---")
            print(f"Age: {profile.age} years")
            print(f"Height: {profile.height_cm} cm")
            print(f"Sex: {profile.sex}")
            print(f"Division: {profile.division}")
            
        # Nutrition Targets
        stmt = select(NutritionPrescription).where(NutritionPrescription.user_id == user.id).order_by(NutritionPrescription.created_at.desc()).limit(1)
        target = (await db.execute(stmt)).scalars().first()
        if target:
            print("\n--- Current Nutrition Target ---")
            print(f"Calories: {target.calories}")
            print(f"Protein: {target.protein_g}g")
            print(f"Carbs: {target.carbs_g}g")
            print(f"Fats: {target.fats_g}g")
            
        # Training Program
        stmt = select(TrainingProgram).where(TrainingProgram.user_id == user.id, TrainingProgram.is_active == True)
        program = (await db.execute(stmt)).scalars().first()
        if program:
            print("\n--- Active Training Program ---")
            print(f"Name: {program.name}")
            print(f"Split: {program.split_type}")
            print(f"Days/Week: {program.days_per_week}")
            
        # Strength Baselines
        stmt = select(StrengthBaseline).where(StrengthBaseline.user_id == user.id)
        baselines = (await db.execute(stmt)).scalars().all()
        if baselines:
            print("\n--- Strength Baselines (1RMs) ---")
            for b in baselines:
                # We can fetch exercise name roughly if we want
                print(f"Exercise ID: {b.exercise_id} | 1RM: {b.one_rm_kg} kg")

        from app.models.diagnostic import PDSLog, HQILog
        stmt = select(PDSLog).where(PDSLog.user_id == user.id).order_by(PDSLog.recorded_date.desc()).limit(1)
        pds = (await db.execute(stmt)).scalars().first()
        if pds:
            print("\n--- PDS Score ---")
            print(f"Score: {pds.pds_score} ({pds.tier})")
            
        from app.services.diagnostic import run_full_diagnostic
        try:
            diag = await run_full_diagnostic(db, user)
            print("\n--- Diagnostic Body Fat ---")
            print(f"Body Fat %: {diag['body_fat']['body_fat_pct']}")
            print(f"Source: {diag['body_fat']['source']}")
            
            print("\n--- Diagnostic Ghost Engine ---")
            print(f"Ghost Mass kg: {diag['ghost_model']['ghost_mass_kg']}")
            print(f"Allometric Multiplier: {diag['ghost_model']['allometric_multiplier']}")
            print(f"Target LBM kg: {diag['weight_cap']['target_lbm_kg']}")
        except Exception as e:
            print(f"Diagnostic error: {e}")
            
        from app.models.measurement import TapeMeasurement
        stmt = select(TapeMeasurement).where(TapeMeasurement.user_id == user.id).order_by(TapeMeasurement.recorded_date.desc()).limit(1)
        tape = (await db.execute(stmt)).scalars().first()
        if tape:
            print("\n--- Raw Tape Measurements ---")
            print(f"Chest: {tape.chest} cm")
            print(f"Shoulders: {tape.shoulders} cm")
            print(f"Waist: {tape.waist} cm")
            print(f"Bicep L/R: {tape.left_bicep} / {tape.right_bicep} cm")
            print(f"Thigh L/R: {tape.left_thigh} / {tape.right_thigh} cm")

if __name__ == "__main__":
    asyncio.run(audit())
