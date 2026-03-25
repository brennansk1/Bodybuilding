import asyncio
from sqlalchemy import select, text
from app.database import async_session
from app.models.user import User
from app.services.demo_seed import seed_demo_admin, DEMO_EMAIL

async def reseed():
    async with async_session() as db:
        # 0. Manual migrations for missing fields in this dev session
        await db.execute(text("ALTER TABLE training_programs ADD COLUMN IF NOT EXISTS custom_template JSONB;"))
        await db.commit()

        # 1. Find and delete existing demo user
        result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        user = result.scalar_one_or_none()
        if user:
            print(f"Deleting existing demo user: {DEMO_EMAIL}")
            await db.delete(user)
            await db.commit()
        
        # 2. Re-run seed
        print("Re-seeding demo admin...")
        created = await seed_demo_admin(db)
        await db.commit()
        if created:
            print("Successfully re-seeded demo admin with advanced measurements.")
        else:
            print("Failed to re-seed demo admin (already exists or error).")

if __name__ == "__main__":
    asyncio.run(reseed())
