import asyncio
import math
from sqlalchemy import select
from app.database import async_session
from app.models.user import User
from app.models.measurement import SkinfoldMeasurement
from app.services.diagnostic import run_full_diagnostic

async def main():
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.username == "samplesk"))).scalar_one_or_none()
        if not user:
            print("User not found.")
            return

        stmt = select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id).order_by(SkinfoldMeasurement.recorded_date.desc()).limit(1)
        sf = (await db.execute(stmt)).scalars().first()
        if not sf:
            print("No skinfolds found.")
            return

        # Set to sum=138 which gives ~19% at age 25
        sf.chest = 16
        sf.midaxillary = 16
        sf.tricep = 14
        sf.subscapular = 22
        sf.abdominal = 30
        sf.suprailiac = 25
        sf.thigh = 15
        
        await db.commit()
        
        # Re-run diagnostic
        diag = await run_full_diagnostic(db, user)
        await db.commit()
        print(f"New Body Fat: {diag['body_fat']['body_fat_pct']}%")
        print("\n--- New PDS ---")
        print(f"{diag['pds']['score']} ({diag['pds']['tier']})")
        
        import json
        print("\n--- New Muscle Gaps ---")
        gaps = diag["muscle_gaps"]["sites"]
        short_gaps = {k: {"gap_cm": v["gap_cm"], "pct_of_ideal": v["pct_of_ideal"]} for k,v in gaps.items()}
        print(json.dumps(short_gaps, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
