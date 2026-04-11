"""
Hardened image upload. Accepts only image MIME types, enforces a strict
extension allow-list, caps size to 8 MB, and writes to an absolute path
independent of the process CWD.
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# Resolve uploads dir relative to the backend package root so it works no
# matter what CWD the app is launched from.
_UPLOAD_ROOT = (Path(__file__).resolve().parents[2] / "uploads").resolve()
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
_ALLOWED_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
_MAX_BYTES = 8 * 1024 * 1024  # 8 MB — plenty for phone photos


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # Extension allow-list (lower-cased, no path component)
    raw_name = os.path.basename(file.filename)
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported extension. Allowed: {', '.join(sorted(_ALLOWED_EXTS))}",
        )

    # MIME allow-list — FastAPI/Starlette sniffs Content-Type from the client
    if file.content_type and file.content_type.lower() not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {file.content_type}",
        )

    # Random safe filename — cannot contain ../ because we use uuid4().hex
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = (_UPLOAD_ROOT / filename).resolve()

    # Defense-in-depth: ensure the resolved path is inside the upload root.
    if _UPLOAD_ROOT not in dest.parents and dest != _UPLOAD_ROOT:
        # _UPLOAD_ROOT must be a parent of dest
        raise HTTPException(status_code=400, detail="Invalid upload path")

    # Streaming size check — abort early if too big.
    total = 0
    try:
        with open(dest, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_BYTES:
                    buffer.close()
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    raise HTTPException(status_code=413, detail="File too large (max 8 MB)")
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Upload failed: %s", exc)
        try:
            if dest.exists():
                os.remove(dest)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail="Upload failed")

    return {"url": f"/uploads/{filename}", "size_bytes": total}
