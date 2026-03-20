from datetime import date

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    sex: str = Field(pattern="^(male|female)$")
    age: int | None = Field(default=None, ge=13, le=80)
    height_cm: float = Field(gt=100, lt=250)
    division: str = Field(pattern="^(mens_open|classic_physique|mens_physique|womens_figure|womens_bikini|womens_physique)$")
    competition_date: date | None = None
    training_experience_years: int = Field(ge=0, le=50)
    wrist_circumference_cm: float | None = Field(default=None, gt=10, lt=25)
    ankle_circumference_cm: float | None = Field(default=None, gt=15, lt=35)


class MeasurementsCreate(BaseModel):
    body_weight_kg: float = Field(gt=30, lt=250)
    # Tape measurements (cm)
    neck: float | None = None
    shoulders: float | None = None
    chest: float | None = None
    left_bicep: float | None = None
    right_bicep: float | None = None
    left_forearm: float | None = None
    right_forearm: float | None = None
    waist: float | None = None
    hips: float | None = None
    left_thigh: float | None = None
    right_thigh: float | None = None
    left_calf: float | None = None
    right_calf: float | None = None
    # Skinfolds (mm)
    sf_chest: float | None = None
    sf_midaxillary: float | None = None
    sf_tricep: float | None = None
    sf_subscapular: float | None = None
    sf_abdominal: float | None = None
    sf_suprailiac: float | None = None
    sf_thigh: float | None = None


class StrengthBaselineCreate(BaseModel):
    exercise_name: str
    one_rm_kg: float = Field(gt=0)


class StrengthBaselinesCreate(BaseModel):
    baselines: list[StrengthBaselineCreate]


class PreferencesCreate(BaseModel):
    training_days_per_week: int = Field(ge=3, le=6, default=4)
    preferred_split: str = Field(default="auto", pattern="^(auto|ppl|upper_lower|full_body|bro_split)$")
    meal_count: int = Field(ge=3, le=6, default=4)
    dietary_restrictions: list[str] = Field(default_factory=list)
    display_name: str | None = Field(default=None, max_length=100)
    cardio_machine: str | None = Field(default=None, pattern="^(treadmill|stairmaster)$")
    cheat_meals_per_week: int | None = Field(default=None, ge=0, le=7)
    intra_workout_nutrition: bool | None = None


class OnboardingCompleteResponse(BaseModel):
    message: str
    pds_score: float | None = None
    tier: str | None = None
