"""
Admin account seed.

Creates a lightweight admin account for dashboard access and admin tasks.
No fake measurement/training data — just credentials and a profile.

Credentials
-----------
  email    : coronado@admin.dev
  password : coronado2024!

Run automatically on startup (idempotent — skipped if user already exists).
"""
import logging

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.profile import UserProfile

logger = logging.getLogger(__name__)
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_EMAIL = "coronado@admin.dev"
ADMIN_PASSWORD = "coronado2024!"
ADMIN_USERNAME = "coronado_admin"


async def seed_admin_account(db: AsyncSession) -> bool:
    """
    Seed the admin account. Returns True if created, False if already exists.
    Idempotent — safe to call every startup.
    """
    existing = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
    if existing.scalar_one_or_none():
        return False

    logger.info("Seeding admin account (%s)…", ADMIN_EMAIL)

    user = User(
        email=ADMIN_EMAIL,
        username=ADMIN_USERNAME,
        hashed_password=_pwd.hash(ADMIN_PASSWORD),
        onboarding_complete=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        sex="male",
        age=30,
        height_cm=178.0,
        division="classic_physique",
        training_experience_years=5,
        wrist_circumference_cm=17.0,
        ankle_circumference_cm=22.0,
        days_per_week=5,
        training_start_time="07:00",
        training_duration_min=75,
        preferences={
            "training_days_per_week": 5,
            "preferred_split": "auto",
            "meal_count": 4,
            "units": "metric",
            "display_name": "Admin",
            "cardio_machine": "treadmill",
            "notifications": {"training": True, "nutrition": True, "checkin": True},
        },
    )
    db.add(profile)
    await db.flush()

    logger.info("Admin account seeded — email: %s", ADMIN_EMAIL)
    return True
