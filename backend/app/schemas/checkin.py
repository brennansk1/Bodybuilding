from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

def _cm(lo: float, hi: float):
    return Field(default=None, gt=lo, lt=hi)

def _sf():
    return Field(default=None, ge=1.0, le=80.0)

class HealthKitPayload(BaseModel):
    """
    iPhone Shortcut → backend payload. Shortcuts can read HealthKit quantities
    (BodyMass, HeartRateVariabilitySDNN, RestingHeartRate, SleepAnalysis) and
    POST them here via X-API-Key auth. Subjective wellness fields (stress,
    mood, energy) are optional — the Shortcut can prompt the user or omit.
    """
    recorded_date: date | None = None
    body_weight_kg: float | None = Field(default=None, gt=30, lt=250)
    # HealthKit only exposes SDNN, not rMSSD. Backend will convert rMSSD ≈ SDNN × 0.8.
    hrv_sdnn_ms: float | None = Field(default=None, gt=0)
    # Alternative field name in case the user's Shortcut already converts to rMSSD.
    hrv_rmssd_ms: float | None = Field(default=None, gt=0)
    resting_hr: float | None = Field(default=None, gt=20, lt=200)
    sleep_hours: float | None = Field(default=None, ge=0, le=16)
    sleep_quality_1_10: float | None = Field(default=None, ge=1, le=10)
    # Optional subjective wellness
    stress_1_10: float | None = Field(default=None, ge=1, le=10)
    mood_1_10: float | None = Field(default=None, ge=1, le=10)
    energy_1_10: float | None = Field(default=None, ge=1, le=10)
    # Informational, not yet persisted (future activity tier)
    step_count: int | None = None
    notes: str | None = None


class DailyCheckin(BaseModel):
    recorded_date: date | None = Field(default=None, description="Date for backfill; defaults to today if omitted")
    body_weight_kg: float | None = Field(default=None, gt=30, lt=250)
    rmssd: float | None = Field(default=None, gt=0)
    resting_hr: float | None = Field(default=None, gt=20, lt=200)
    sleep_quality: float | None = Field(default=None, ge=1, le=10)
    sleep_hours: float | None = Field(default=None, ge=0, le=16)   # actual sleep duration
    soreness_score: float | None = Field(default=None, ge=1, le=10)
    sore_muscles: list[str] | None = Field(default_factory=list)
    # Subjective wellness — critical signals an Olympia coach asks about daily.
    stress_score: float | None = Field(default=None, ge=1, le=10)   # 1 = calm, 10 = crushed
    mood_score: float | None = Field(default=None, ge=1, le=10)     # 1 = terrible, 10 = great
    energy_score: float | None = Field(default=None, ge=1, le=10)   # 1 = exhausted, 10 = buzzing
    nutrition_adherence_pct: float | None = Field(default=None, ge=0, le=100)
    training_adherence_pct: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None

class WeeklyCheckinRequest(BaseModel):
    # Biological Data (Tape)
    neck: float | None = _cm(20, 65)
    shoulders: float | None = _cm(80, 200)
    chest: float | None = _cm(60, 180)
    left_bicep: float | None = _cm(20, 65)
    right_bicep: float | None = _cm(20, 65)
    left_forearm: float | None = _cm(15, 50)
    right_forearm: float | None = _cm(15, 50)
    waist: float | None = _cm(40, 160)
    hips: float | None = _cm(50, 180)
    left_thigh: float | None = _cm(30, 100)
    right_thigh: float | None = _cm(30, 100)
    left_calf: float | None = _cm(20, 70)
    right_calf: float | None = _cm(20, 70)
    
    # Advanced isolation tape sites
    chest_relaxed: float | None = _cm(60, 180)
    chest_lat_spread: float | None = _cm(60, 200)
    back_width: float | None = _cm(20, 80)
    left_proximal_thigh: float | None = _cm(30, 100)
    right_proximal_thigh: float | None = _cm(30, 100)
    left_distal_thigh: float | None = _cm(20, 80)
    right_distal_thigh: float | None = _cm(20, 80)

    # Skinfolds
    sf_chest: float | None = _sf()
    sf_midaxillary: float | None = _sf()
    sf_tricep: float | None = _sf()
    sf_subscapular: float | None = _sf()
    sf_abdominal: float | None = _sf()
    sf_suprailiac: float | None = _sf()
    sf_thigh: float | None = _sf()
    sf_bicep: float | None = _sf()
    sf_lower_back: float | None = _sf()
    sf_calf: float | None = _sf()

    # Direct body composition (from Fit3D, DEXA, InBody — bypasses JP7 formula)
    body_fat_pct: float | None = Field(default=None, ge=3.0, le=60.0)
    lean_mass_kg: float | None = Field(default=None, gt=20, lt=200)
    fat_mass_kg: float | None = Field(default=None, gt=1, lt=200)
    scan_source: str | None = None  # "fit3d" | "dexa" | "inbody" | "tape"

    # Photos and notes
    front_photo_url: str | None = None
    back_photo_url: str | None = None
    side_left_photo_url: str | None = None
    side_right_photo_url: str | None = None
    front_pose_photo_url: str | None = None
    back_pose_photo_url: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "WeeklyCheckinRequest":
        if self.shoulders and self.waist and self.shoulders <= self.waist:
            raise ValueError("Shoulders measurement must be larger than waist")
        if self.chest and self.waist and self.chest <= self.waist * 0.7:
            raise ValueError("Chest measurement seems too small relative to waist")
        return self
