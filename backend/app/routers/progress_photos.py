from __future__ import annotations

"""Progress photo upload + retrieval.

Stores a photo to the app's media directory (configurable via
`PHOTO_MEDIA_DIR` env var, defaults to `./uploads/photos/`) and persists
the metadata row (date + pose_type) so the overlay comparison can align
like-for-like poses.

File storage is local-only for now; moving to S3/R2 later is a drop-in
swap of the `_save_file` helper.
"""

import logging
import os
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.progress_photo import ProgressPhoto, POSE_TYPES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/progress", tags=["progress"])


# Default: <backend>/uploads/photos/<user_id>/<photo_id>.<ext>
MEDIA_ROOT = Path(os.environ.get("PHOTO_MEDIA_DIR", "./uploads/photos")).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


def _save_file(user_id: uuid.UUID, photo_id: uuid.UUID, upload: UploadFile) -> str:
    """Write to disk; return the public URL path we serve from."""
    suffix = ""
    if upload.filename:
        suffix = Path(upload.filename).suffix[:6]  # cap length
    user_dir = MEDIA_ROOT / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{photo_id}{suffix}"
    content = upload.file.read()
    dest.write_bytes(content)
    # Served via /api/v1/progress/photos/{photo_id} (GET)
    return f"/api/v1/progress/photos/{photo_id}/file"


@router.post("/photos")
async def upload_photo(
    photo_date: str = Form(...),
    pose_type: str = Form("free_form"),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if pose_type not in POSE_TYPES:
        raise HTTPException(400, f"pose_type must be one of {list(POSE_TYPES)}")
    try:
        parsed_date = date.fromisoformat(photo_date)
    except ValueError:
        raise HTTPException(400, "photo_date must be ISO format (YYYY-MM-DD)")

    photo_id = uuid.uuid4()
    url = _save_file(user.id, photo_id, file)

    row = ProgressPhoto(
        id=photo_id,
        user_id=user.id,
        photo_date=parsed_date,
        pose_type=pose_type,
        storage_url=url,
        notes=(notes or "").strip() or None,
    )
    db.add(row)
    await db.flush()
    return {
        "id": str(photo_id),
        "photo_date": photo_date,
        "pose_type": pose_type,
        "storage_url": url,
    }


@router.get("/photos")
async def list_photos(
    pose_type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ProgressPhoto).where(ProgressPhoto.user_id == user.id)
    if pose_type:
        if pose_type not in POSE_TYPES:
            raise HTTPException(400, f"unknown pose_type '{pose_type}'")
        q = q.where(ProgressPhoto.pose_type == pose_type)
    rows = (await db.execute(q.order_by(asc(ProgressPhoto.photo_date)))).scalars().all()
    return [
        {
            "id": str(r.id),
            "photo_date": r.photo_date.isoformat(),
            "pose_type": r.pose_type,
            "storage_url": r.storage_url,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.get("/photos/{photo_id}/file")
async def get_photo_file(
    photo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(ProgressPhoto).where(
            ProgressPhoto.id == photo_id,
            ProgressPhoto.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "photo not found")
    # Find file on disk by id (suffix-agnostic).
    user_dir = MEDIA_ROOT / str(user.id)
    for f in user_dir.iterdir():
        if f.stem == str(photo_id):
            return FileResponse(f)
    raise HTTPException(404, "photo file missing on disk")


@router.delete("/photos/{photo_id}")
async def delete_photo(
    photo_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(ProgressPhoto).where(
            ProgressPhoto.id == photo_id,
            ProgressPhoto.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "photo not found")
    # Remove file
    user_dir = MEDIA_ROOT / str(user.id)
    for f in user_dir.iterdir():
        if f.stem == str(photo_id):
            try:
                f.unlink()
            except OSError:
                pass
    await db.delete(row)
    return {"ok": True}


@router.get("/poses")
async def list_pose_types():
    """Expose the canonical pose list for the upload form."""
    return {"pose_types": list(POSE_TYPES)}
