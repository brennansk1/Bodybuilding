import uuid
from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.profile import UserProfile
from app.models.measurement import BodyWeightLog, SkinfoldMeasurement, TapeMeasurement
from app.models.nutrition import (
    NutritionPrescription, AdherenceLog, IngredientMaster, UserMeal, MealItem,
)
from app.models.training import ARILog

router = APIRouter(prefix="/engine3", tags=["engine3-nutrition"])


# ---------------------------------------------------------------------------
# Prescription
# ---------------------------------------------------------------------------

@router.get("/prescription/current")
async def get_current_prescription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at))
        .limit(1)
    )
    rx = result.scalar_one_or_none()
    if not rx:
        # Generate initial prescription from profile + latest weight
        profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Complete onboarding first")

        bw_result = await db.execute(
            select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
            .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
        )
        bw = bw_result.scalar_one_or_none()
        if not bw:
            raise HTTPException(status_code=404, detail="No body weight data")

        from app.engines.engine3.macros import compute_tdee, compute_macros
        from app.engines.engine1.body_fat import navy_body_fat, lean_mass_kg as calc_lean_mass

        # PAL multiplier derived from training days per week.
        # Heavy resistance training raises EPOC and daily protein turnover costs
        # beyond what acute calorie burn suggests — 5-day training uses 1.65, not 1.55.
        training_days = (profile.preferences or {}).get("training_days_per_week", 4)
        if training_days <= 2:
            pal = 1.375   # light
        elif training_days <= 4:
            pal = 1.55    # moderate
        elif training_days == 5:
            pal = 1.65    # active — heavy compound training 5 days
        else:
            pal = 1.725   # very active — 6+ days

        tdee = compute_tdee(
            weight_kg=bw.weight_kg,
            height_cm=profile.height_cm,
            age=profile.age or 25,
            sex=profile.sex,
            activity_multiplier=pal,
        )
        # Compute lean mass for protein/fat targets: use skinfold BF% if available,
        # else Navy circumference estimate from latest tape measurement.
        lbm = None
        sf_result = await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
            .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
        )
        sf = sf_result.scalar_one_or_none()
        bf_pct = sf.body_fat_pct if sf else None
        if bf_pct is None:
            tape_result = await db.execute(
                select(TapeMeasurement).where(TapeMeasurement.user_id == user.id)
                .order_by(desc(TapeMeasurement.recorded_date), desc(TapeMeasurement.created_at)).limit(1)
            )
            tape = tape_result.scalar_one_or_none()
            if tape and tape.waist and tape.neck and profile.height_cm:
                try:
                    bf_pct = navy_body_fat(tape.waist, tape.neck, profile.height_cm, profile.sex, tape.hips)
                except Exception:
                    pass
        if bf_pct is not None:
            lbm = calc_lean_mass(bw.weight_kg, bf_pct)
        macros = compute_macros(tdee, "maintain", bw.weight_kg, profile.sex, lean_mass_kg=lbm)

        rx = NutritionPrescription(
            user_id=user.id,
            tdee=tdee,
            target_calories=macros["target_calories"],
            protein_g=macros["protein_g"],
            carbs_g=macros["carbs_g"],
            fat_g=macros["fat_g"],
            phase="maintain",
            is_active=True,
        )
        db.add(rx)
        await db.flush()

    from app.engines.engine3.macros import (
        compute_training_rest_day_macros,
        compute_peri_workout_carb_split,
        compute_division_nutrition_priorities,
    )
    base_macros = {
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
        "target_calories": rx.target_calories,
    }

    bw_result2 = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw2 = bw_result2.scalar_one_or_none()
    weight_kg = bw2.weight_kg if bw2 else 80.0

    # Load profile for division-specific nutrition priorities
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    rx_profile = profile_result.scalar_one_or_none()
    division = getattr(rx_profile, "division", "mens_open") or "mens_open"
    phase = rx.phase or "maintain"

    # Division-specific carb cycling factor overrides the default ±20%
    div_nutrition = compute_division_nutrition_priorities(division, phase)
    cycling_factor = div_nutrition["carb_cycling_factor"]

    # Recompute training/rest day macros with division-specific carb swing
    train_carbs = round(base_macros["carbs_g"] * (1.0 + cycling_factor), 1)
    rest_carbs = round(base_macros["carbs_g"] * (1.0 - cycling_factor), 1)
    fat_floor = round(div_nutrition["fat_per_kg_floor"] * weight_kg, 1)

    from app.engines.engine3.macros import _KCAL_PER_G_CARB, _KCAL_PER_G_FAT
    extra_kcal = (train_carbs - base_macros["carbs_g"]) * _KCAL_PER_G_CARB
    train_fat = round(max(fat_floor, base_macros["fat_g"] - extra_kcal / _KCAL_PER_G_FAT), 1)
    saved_kcal = (base_macros["carbs_g"] - rest_carbs) * _KCAL_PER_G_CARB
    rest_fat = round(base_macros["fat_g"] + saved_kcal / _KCAL_PER_G_FAT, 1)

    train_kcal = round(base_macros["protein_g"] * 4 + train_carbs * 4 + train_fat * 9, 0)
    rest_kcal  = round(base_macros["protein_g"] * 4 + rest_carbs  * 4 + rest_fat  * 9, 0)
    cycling = {
        "training_day": {
            "protein_g": base_macros["protein_g"],
            "carbs_g": train_carbs,
            "fat_g": train_fat,
            "calories": train_kcal,
            "target_calories": train_kcal,
        },
        "rest_day": {
            "protein_g": base_macros["protein_g"],
            "carbs_g": rest_carbs,
            "fat_g": rest_fat,
            "calories": rest_kcal,
            "target_calories": rest_kcal,
        },
    }
    peri = compute_peri_workout_carb_split(train_carbs, div_nutrition["meal_frequency_target"])

    # Alias with field names the frontend expects
    peri_timing_alias = {
        "pre_workout_carbs_g": peri["pre_workout_g"],
        "intra_workout_carbs_g": peri["intra_workout_g"],
        "post_workout_carbs_g": peri["post_workout_g"],
        "other_carbs_g": peri["other_meals_g"],
    }

    return {
        "tdee": rx.tdee,
        "target_calories": rx.target_calories,
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
        "peri_workout_carb_pct": rx.peri_workout_carb_pct,
        "phase": rx.phase,
        "training_day_macros": cycling["training_day"],
        "rest_day_macros": cycling["rest_day"],
        "peri_workout_carbs": peri,
        "peri_workout_timing": peri_timing_alias,
        "division_nutrition": {
            "carb_cycling_factor": cycling_factor,
            "meal_frequency_target": div_nutrition["meal_frequency_target"],
            "mps_threshold_g": div_nutrition["mps_threshold_g"],
            "notes": div_nutrition["notes"],
        },
    }


# ---------------------------------------------------------------------------
# Peak week
# ---------------------------------------------------------------------------

@router.get("/peak-week")
async def get_peak_week(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    competition_date = profile.competition_date
    if not competition_date:
        raise HTTPException(status_code=400, detail="No competition date set in profile")

    today = date_cls.today()
    days_out = (competition_date - today).days
    if days_out > 21:
        raise HTTPException(status_code=400, detail=f"Peak week protocol activates within 21 days of competition ({days_out} days out)")

    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    if not bw:
        raise HTTPException(status_code=404, detail="No body weight data")

    sf_result = await db.execute(
        select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
        .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
    )
    sf = sf_result.scalar_one_or_none()

    from app.engines.engine3.peak_week import compute_peak_week_protocol
    from app.engines.engine1.body_fat import lean_mass_kg

    if sf and sf.body_fat_pct:
        lbm = lean_mass_kg(bw.weight_kg, sf.body_fat_pct)
    else:
        lbm = bw.weight_kg * 0.85

    protocol = compute_peak_week_protocol(lean_mass_kg=lbm, show_date=competition_date)

    return {
        "protocol": protocol,
        "show_date": str(competition_date),
        "days_out": days_out,
    }


# ---------------------------------------------------------------------------
# Adherence
# ---------------------------------------------------------------------------

@router.get("/adherence")
async def get_adherence_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdherenceLog).where(AdherenceLog.user_id == user.id)
        .order_by(desc(AdherenceLog.recorded_date), desc(AdherenceLog.created_at)).limit(12)
    )
    logs = result.scalars().all()
    return [
        {
            "date": str(log.recorded_date),
            "nutrition": log.nutrition_adherence_pct,
            "training": log.training_adherence_pct,
            "overall": log.overall_adherence_pct,
        }
        for log in reversed(logs)
    ]


# ---------------------------------------------------------------------------
# Autoregulation
# ---------------------------------------------------------------------------

@router.post("/autoregulation")
async def run_autoregulation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at))
        .limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=404, detail="No active prescription")

    adh_result = await db.execute(
        select(AdherenceLog).where(AdherenceLog.user_id == user.id)
        .order_by(desc(AdherenceLog.recorded_date), desc(AdherenceLog.created_at)).limit(1)
    )
    adh = adh_result.scalar_one_or_none()

    # Load profile for sex and phase
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    sex = getattr(profile, "sex", "male") or "male"
    phase = rx.phase or "maintain"

    # EWMA weight tracking — compute smoothed rate of change from last 28 days
    from app.engines.engine3.kinetic import compute_rate_of_change_detailed
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(BodyWeightLog.recorded_date)
        .limit(28)
    )
    bw_logs = bw_result.scalars().all()
    ewma_rate = None
    trend_direction = "stable"
    if len(bw_logs) >= 2:
        weight_history = [(str(bw.recorded_date), bw.weight_kg) for bw in bw_logs]
        cycle_day = (profile.preferences or {}).get("current_cycle_day") if profile else None
        try:
            rate_detail = compute_rate_of_change_detailed(weight_history, sex=sex, cycle_day=cycle_day)
            ewma_rate = rate_detail["rate_kg_per_week"]
            trend_direction = rate_detail["trend_direction"]
        except (ValueError, Exception):
            pass

    # Metabolic adaptation — compute weeks in deficit from prescription creation date
    from app.engines.engine3.thermodynamic import compute_adapted_tdee
    adapted_tdee = rx.tdee
    weeks_in_deficit = 0.0
    if phase in ("cut", "peak_week") and rx.created_at:
        weeks_in_deficit = (date_cls.today() - rx.created_at.date()).days / 7.0
        if weeks_in_deficit > 0:
            adapted_tdee = compute_adapted_tdee(rx.tdee, weeks_in_deficit)

    # ARI-triggered refeed check — query last 5 days of ARI scores
    from app.engines.engine3.autoregulation import check_ari_triggered_refeed, adherence_lock
    five_days_ago = date_cls.today() - timedelta(days=5)
    ari_result = await db.execute(
        select(ARILog)
        .where(ARILog.user_id == user.id, ARILog.recorded_date >= five_days_ago)
        .order_by(ARILog.recorded_date)
    )
    recent_ari_logs = ari_result.scalars().all()
    refeed_check = None
    if recent_ari_logs:
        # Get current BF% for refeed threshold
        sf_result = await db.execute(
            select(SkinfoldMeasurement).where(SkinfoldMeasurement.user_id == user.id)
            .order_by(desc(SkinfoldMeasurement.recorded_date), desc(SkinfoldMeasurement.created_at)).limit(1)
        )
        sf = sf_result.scalar_one_or_none()
        current_bf_pct = sf.body_fat_pct if sf else 15.0
        try:
            refeed_check = check_ari_triggered_refeed(
                recent_ari_scores=[log.ari_score for log in recent_ari_logs],
                phase=phase,
                current_bf_pct=current_bf_pct,
                sex=sex,
            )
        except (ValueError, Exception):
            pass

    # Adherence lock — applies macro reduction at <85% adherence
    adherence_pct = adh.overall_adherence_pct if adh else 100.0
    base_macros = {
        "target_calories": rx.target_calories,
        "protein_g": rx.protein_g,
        "carbs_g": rx.carbs_g,
        "fat_g": rx.fat_g,
    }
    locked = adherence_lock(adherence_pct, base_macros)

    return {
        **locked,
        "metabolic_adaptation": {
            "weeks_in_deficit": round(weeks_in_deficit, 1),
            "adapted_tdee": adapted_tdee,
            "adaptation_active": weeks_in_deficit > 0 and phase in ("cut", "peak_week"),
        },
        "weight_trend": {
            "ewma_rate_kg_per_week": ewma_rate,
            "trend_direction": trend_direction,
        },
        "ari_refeed": refeed_check,
    }


# ---------------------------------------------------------------------------
# Restoration (post-show reverse diet)
# ---------------------------------------------------------------------------

@router.get("/prescription/restoration")
async def get_restoration_prescription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the post-show restoration (reverse diet) macro prescription.
    Activates when competition_date is in the past.
    """
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    competition_date = profile.competition_date
    if not competition_date or competition_date > date_cls.today():
        raise HTTPException(
            status_code=400,
            detail="Restoration phase requires a past competition date. Set your show date in profile."
        )

    weeks_post_show = (date_cls.today() - competition_date).days // 7
    if weeks_post_show < 1:
        weeks_post_show = 1

    # Get current weight and TDEE baseline
    bw_result = await db.execute(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(desc(BodyWeightLog.recorded_date), desc(BodyWeightLog.created_at)).limit(1)
    )
    bw = bw_result.scalar_one_or_none()
    if not bw:
        raise HTTPException(status_code=404, detail="No body weight data")

    # Use TDEE from active prescription, or compute fresh
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .order_by(desc(NutritionPrescription.created_at)).limit(1)
    )
    rx = rx_result.scalar_one_or_none()
    base_tdee = rx.tdee if rx else 2200.0

    from app.engines.engine3.macros import compute_restoration_macros
    sex = getattr(profile, "sex", "male") or "male"
    restoration = compute_restoration_macros(
        base_tdee=base_tdee,
        weight_kg=bw.weight_kg,
        sex=sex,
        weeks_post_show=weeks_post_show,
    )

    return {
        "phase": "restoration",
        "weeks_post_show": weeks_post_show,
        "competition_date": str(competition_date),
        **restoration,
    }


# ---------------------------------------------------------------------------
# Ingredient search
# ---------------------------------------------------------------------------

@router.get("/ingredients/search")
async def search_ingredients(
    q: str = "",
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(IngredientMaster)
    if q:
        query = query.where(IngredientMaster.name.ilike(f"%{q}%"))
    if category:
        query = query.where(IngredientMaster.category == category)
    query = query.order_by(IngredientMaster.protein_per_100g.desc()).limit(20)

    result = await db.execute(query)
    ingredients = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "name": i.name,
            "category": i.category,
            "calories_per_100g": i.calories_per_100g,
            "protein_per_100g": i.protein_per_100g,
            "carbs_per_100g": i.carbs_per_100g,
            "fat_per_100g": i.fat_per_100g,
            "fiber_per_100g": i.fiber_per_100g,
            "is_peri_workout": i.is_peri_workout,
        }
        for i in ingredients
    ]


# ---------------------------------------------------------------------------
# Meal logging
# ---------------------------------------------------------------------------

class MealItemCreate(BaseModel):
    ingredient_id: str
    quantity_g: float = Field(gt=0, le=2000)


class MealCreate(BaseModel):
    meal_number: int = Field(ge=1, le=8)
    meal_type: str = "standard"  # standard / pre_workout / post_workout
    items: list[MealItemCreate]


def _macro_for_item(ingredient: IngredientMaster, quantity_g: float) -> dict:
    scale = quantity_g / 100.0
    return {
        "calories": round(ingredient.calories_per_100g * scale, 1),
        "protein_g": round(ingredient.protein_per_100g * scale, 1),
        "carbs_g": round(ingredient.carbs_per_100g * scale, 1),
        "fat_g": round(ingredient.fat_per_100g * scale, 1),
    }


@router.post("/meals")
async def log_meal(
    data: MealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date_cls.today()

    meal_type = data.meal_type if data.meal_type in ("standard", "pre_workout", "post_workout") else "standard"
    meal = UserMeal(
        user_id=user.id,
        meal_number=data.meal_number,
        meal_type=meal_type,
        recorded_date=today,
    )
    db.add(meal)
    await db.flush()

    total_cal = total_prot = total_carbs = total_fat = 0.0
    items_out = []

    for item_data in data.items:
        ing_result = await db.execute(
            select(IngredientMaster).where(
                IngredientMaster.id == uuid.UUID(item_data.ingredient_id)
            )
        )
        ingredient = ing_result.scalar_one_or_none()
        if not ingredient:
            continue

        meal_item = MealItem(
            meal_id=meal.id,
            ingredient_id=ingredient.id,
            quantity_g=item_data.quantity_g,
        )
        db.add(meal_item)

        macros = _macro_for_item(ingredient, item_data.quantity_g)
        total_cal += macros["calories"]
        total_prot += macros["protein_g"]
        total_carbs += macros["carbs_g"]
        total_fat += macros["fat_g"]

        items_out.append({
            "ingredient_name": ingredient.name,
            "quantity_g": item_data.quantity_g,
            **macros,
        })

    await db.flush()

    return {
        "id": str(meal.id),
        "meal_number": meal.meal_number,
        "meal_type": meal.meal_type,
        "items": items_out,
        "totals": {
            "calories": round(total_cal, 1),
            "protein_g": round(total_prot, 1),
            "carbs_g": round(total_carbs, 1),
            "fat_g": round(total_fat, 1),
        },
    }


@router.get("/meals/{meal_date}")
async def get_meals_for_date(
    meal_date: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date_cls.fromisoformat(meal_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await db.execute(
        select(UserMeal)
        .where(UserMeal.user_id == user.id, UserMeal.recorded_date == target_date)
        .order_by(UserMeal.meal_number)
    )
    meals = result.scalars().all()

    meals_out = []
    for meal in meals:
        items_result = await db.execute(
            select(MealItem, IngredientMaster)
            .join(IngredientMaster, MealItem.ingredient_id == IngredientMaster.id)
            .where(MealItem.meal_id == meal.id)
        )
        items = items_result.all()

        total_cal = total_prot = total_carbs = total_fat = 0.0
        items_out = []
        for mi, ing in items:
            macros = _macro_for_item(ing, mi.quantity_g)
            total_cal += macros["calories"]
            total_prot += macros["protein_g"]
            total_carbs += macros["carbs_g"]
            total_fat += macros["fat_g"]
            items_out.append({"ingredient_name": ing.name, "quantity_g": mi.quantity_g, **macros})

        meals_out.append({
            "id": str(meal.id),
            "meal_number": meal.meal_number,
            "meal_type": meal.meal_type,
            "items": items_out,
            "totals": {
                "calories": round(total_cal, 1),
                "protein_g": round(total_prot, 1),
                "carbs_g": round(total_carbs, 1),
                "fat_g": round(total_fat, 1),
            },
        })

    return meals_out


@router.get("/daily-totals/{meal_date}")
async def get_daily_totals(
    meal_date: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date_cls.fromisoformat(meal_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await db.execute(
        select(UserMeal)
        .where(UserMeal.user_id == user.id, UserMeal.recorded_date == target_date)
    )
    meals = result.scalars().all()

    MPS_THRESHOLD = 30
    total_cal = total_prot = total_carbs = total_fat = 0.0
    meal_protein_totals = []

    for meal in meals:
        items_result = await db.execute(
            select(MealItem, IngredientMaster)
            .join(IngredientMaster, MealItem.ingredient_id == IngredientMaster.id)
            .where(MealItem.meal_id == meal.id)
        )
        meal_prot = 0.0
        for mi, ing in items_result.all():
            macros = _macro_for_item(ing, mi.quantity_g)
            total_cal += macros["calories"]
            total_prot += macros["protein_g"]
            total_carbs += macros["carbs_g"]
            total_fat += macros["fat_g"]
            meal_prot += macros["protein_g"]
        meal_protein_totals.append(meal_prot)

    # MPS assessment
    mps_meals = sum(1 for p in meal_protein_totals if p >= MPS_THRESHOLD)
    total_meals = len(meal_protein_totals)
    mps_score = min(100, round((mps_meals / 4) * 100))

    if mps_meals == 0:
        mps_guidance = "No MPS-stimulating meals yet today. Aim for 30g+ protein per meal, 4 times."
    elif mps_meals < 3:
        mps_guidance = f"{mps_meals} MPS-stimulating meal(s) so far. Target 4 meals with 30g+ protein spread evenly."
    elif mps_meals == 3:
        mps_guidance = "Good — 3 MPS meals hit. One more high-protein meal to reach optimal stimulation."
    else:
        mps_guidance = "Excellent — 4+ MPS-stimulating meals. Protein distribution is optimal."

    # Compare against active prescription
    rx_result = await db.execute(
        select(NutritionPrescription)
        .where(NutritionPrescription.user_id == user.id, NutritionPrescription.is_active == True)
        .limit(1)
    )
    rx = rx_result.scalar_one_or_none()

    return {
        "date": meal_date,
        "total_calories": round(total_cal, 1),
        "total_protein_g": round(total_prot, 1),
        "total_carbs_g": round(total_carbs, 1),
        "total_fat_g": round(total_fat, 1),
        "target_calories": rx.target_calories if rx else None,
        "remaining_calories": round(rx.target_calories - total_cal, 1) if rx else None,
        "mps_assessment": {
            "mps_threshold_meals": mps_meals,
            "total_meals": total_meals,
            "score": mps_score,
            "guidance": mps_guidance,
        },
    }
