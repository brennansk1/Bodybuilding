import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IngredientMaster(Base):
    __tablename__ = "ingredients_master"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # protein/carb/fat/vegetable/fruit
    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_per_100g: Mapped[float] = mapped_column(Float, default=0)
    glycemic_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_peri_workout: Mapped[bool] = mapped_column(default=False)


class NutritionPrescription(Base):
    __tablename__ = "nutrition_prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    tdee: Mapped[float] = mapped_column(Float, nullable=False)
    target_calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    peri_workout_carb_pct: Mapped[float] = mapped_column(Float, default=0.4)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)  # bulk/cut/maintain/peak
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="nutrition_prescriptions")


class UserMeal(Base):
    __tablename__ = "user_meals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    meal_number: Mapped[int] = mapped_column(Integer, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(30), nullable=False)  # pre_workout/post_workout/standard
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["MealItem"]] = relationship(back_populates="meal", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_meals_user_date", "user_id", "recorded_date"),)


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_meals.id", ondelete="CASCADE"))
    ingredient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ingredients_master.id"))
    quantity_g: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    meal: Mapped["UserMeal"] = relationship(back_populates="items")
    ingredient: Mapped["IngredientMaster"] = relationship()


class NutritionLog(Base):
    __tablename__ = "nutrition_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_calories: Mapped[float] = mapped_column(Float, nullable=False)
    total_protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    total_carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    total_fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_nutrition_log_user_date", "user_id", "recorded_date"),)


class AdherenceLog(Base):
    __tablename__ = "adherence_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    nutrition_adherence_pct: Mapped[float] = mapped_column(Float, nullable=False)
    training_adherence_pct: Mapped[float] = mapped_column(Float, nullable=False)
    overall_adherence_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_adherence_user_date", "user_id", "recorded_date"),)


class WeeklyCheckin(Base):
    __tablename__ = "weekly_checkins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Biological
    body_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    # HRV
    avg_rmssd: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_resting_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_sleep_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    soreness_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1-10
    # Adherence
    nutrition_adherence_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_adherence_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Engine outputs (filled after processing)
    pds_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ari_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    front_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    back_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    side_left_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    side_right_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    front_pose_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    back_pose_photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="weekly_checkins")

    __table_args__ = (Index("ix_checkin_user_date", "user_id", "checkin_date"),)
