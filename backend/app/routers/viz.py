"""
Visualization Router — returns Plotly JSON for all 5 dashboard charts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.diagnostic import HQILog, PDSLog
from app.models.training import ARILog
from app.models.nutrition import AdherenceLog
from app.visualizations.charts import (
    generate_spider_plot,
    generate_pds_glide_path,
    generate_autonomic_gauge,
    generate_adherence_grid,
    generate_hypertrophy_heatmap,
)

router = APIRouter(prefix="/viz", tags=["visualizations"])


@router.get("/spider-plot")
async def spider_plot(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    hqi = result.scalar_one_or_none()
    if not hqi:
        raise HTTPException(status_code=404, detail="No HQI data")

    return generate_spider_plot(hqi.site_scores, hqi.overall_hqi)


@router.get("/pds-glide-path")
async def pds_glide_path(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PDSLog).where(PDSLog.user_id == user.id).order_by(PDSLog.recorded_date)
    )
    logs = result.scalars().all()
    if not logs:
        raise HTTPException(status_code=404, detail="No PDS data")

    history = [(str(log.recorded_date), log.pds_score, log.tier) for log in logs]
    return generate_pds_glide_path(history)


@router.get("/autonomic-gauge")
async def autonomic_gauge(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ARILog).where(ARILog.user_id == user.id).order_by(desc(ARILog.recorded_date), desc(ARILog.created_at)).limit(1)
    )
    ari = result.scalar_one_or_none()
    if not ari:
        raise HTTPException(status_code=404, detail="No ARI data")

    return generate_autonomic_gauge(ari.ari_score)


@router.get("/adherence-grid")
async def adherence_grid(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdherenceLog)
        .where(AdherenceLog.user_id == user.id)
        .order_by(AdherenceLog.recorded_date)
        .limit(12)
    )
    logs = result.scalars().all()
    if not logs:
        raise HTTPException(status_code=404, detail="No adherence data")

    data = [
        (str(log.recorded_date), log.nutrition_adherence_pct, log.training_adherence_pct)
        for log in logs
    ]
    return generate_adherence_grid(data)


@router.get("/hypertrophy-heatmap")
async def hypertrophy_heatmap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HQILog).where(HQILog.user_id == user.id).order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    hqi = result.scalar_one_or_none()
    if not hqi:
        raise HTTPException(status_code=404, detail="No HQI data")

    return generate_hypertrophy_heatmap(hqi.site_scores)
