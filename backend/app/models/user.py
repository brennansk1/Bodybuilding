import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HealthKitApiKey(Base):
    """
    Long-lived per-device API keys for HealthKit / iPhone Shortcut ingest.
    Each key authenticates POST /checkin/daily/healthkit without needing
    a refreshable JWT. Keys are never returned in plaintext after creation —
    the client must store them on device.
    """
    __tablename__ = "healthkit_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    # We store a SHA-256 hex digest — never the plaintext key.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Short human prefix (first 6 chars of the plaintext) so the settings UI
    # can show "hk_XXXXXX…" for identification without leaking the full key.
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(255), default="iPhone Shortcut")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    body_weight_logs: Mapped[list["BodyWeightLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tape_measurements: Mapped[list["TapeMeasurement"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    skinfold_measurements: Mapped[list["SkinfoldMeasurement"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    strength_baselines: Mapped[list["StrengthBaseline"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    strength_logs: Mapped[list["StrengthLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    lcsa_logs: Mapped[list["LCSALog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pds_logs: Mapped[list["PDSLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    hqi_logs: Mapped[list["HQILog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    hrv_logs: Mapped[list["HRVLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ari_logs: Mapped[list["ARILog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    training_programs: Mapped[list["TrainingProgram"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    nutrition_prescriptions: Mapped[list["NutritionPrescription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weekly_checkins: Mapped[list["WeeklyCheckin"]] = relationship(back_populates="user", cascade="all, delete-orphan")
