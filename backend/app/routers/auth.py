import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# In-memory sliding-window rate limiter (per IP, no external dependency)
# ---------------------------------------------------------------------------

_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 900   # 15-minute window
_RATE_MAX = 10       # max auth attempts per window per IP


def _rate_limit(request: Request) -> None:
    """Raise 429 if the client IP exceeds the auth rate limit."""
    ip = (request.client.host if request.client else None) or "unknown"
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW
    attempts = [t for t in _login_attempts[ip] if t > cutoff]
    _login_attempts[ip] = attempts
    if len(attempts) >= _RATE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again in 15 minutes.",
            headers={"Retry-After": "900"},
        )
    _login_attempts[ip].append(now)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "access"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "refresh"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, request: Request, db: AsyncSession = Depends(get_db), _rl: None = Depends(_rate_limit)):
    existing = await db.execute(select(User).where((User.email == data.email) | (User.username == data.username)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already registered")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=pwd_context.hash(data.password),
    )
    db.add(user)
    await db.flush()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request, db: AsyncSession = Depends(get_db), _rl: None = Depends(_rate_limit)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: TokenRefresh):
    try:
        payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.profile import UserProfile
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    display_name = None
    if profile and profile.preferences:
        display_name = profile.preferences.get("display_name")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        onboarding_complete=user.onboarding_complete,
        display_name=display_name,
    )


# ---------------------------------------------------------------------------
# HealthKit / iPhone Shortcut API keys
# ---------------------------------------------------------------------------

import secrets as _secrets

from app.dependencies import hash_api_key
from app.models.user import HealthKitApiKey


class ApiKeyCreate(BaseModel):
    label: str = "iPhone Shortcut"


@router.post("/api-keys")
async def create_api_key(
    data: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new HealthKit API key. The plaintext key is shown ONCE in the
    response and never stored — the backend keeps only a SHA-256 hash.
    """
    raw = "hk_" + _secrets.token_urlsafe(32)
    prefix = raw[:10]
    key_obj = HealthKitApiKey(
        user_id=user.id,
        api_key_hash=hash_api_key(raw),
        key_prefix=prefix,
        label=data.label[:255] if data.label else "iPhone Shortcut",
    )
    db.add(key_obj)
    await db.commit()
    return {
        "id": str(key_obj.id),
        "api_key": raw,
        "key_prefix": prefix,
        "label": key_obj.label,
        "created_at": key_obj.created_at.isoformat() if key_obj.created_at else None,
        "warning": (
            "Store this key now — we only ever show it once. "
            "If you lose it, generate a new one and revoke the old."
        ),
    }


@router.get("/api-keys")
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthKitApiKey)
        .where(HealthKitApiKey.user_id == user.id, HealthKitApiKey.revoked_at.is_(None))
        .order_by(desc(HealthKitApiKey.created_at))
    )
    keys = result.scalars().all()
    return [
        {
            "id": str(k.id),
            "key_prefix": k.key_prefix,
            "label": k.label,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    try:
        uuid_val = _uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key id")

    result = await db.execute(
        select(HealthKitApiKey).where(
            HealthKitApiKey.id == uuid_val,
            HealthKitApiKey.user_id == user.id,
        )
    )
    key_obj = result.scalar_one_or_none()
    if not key_obj:
        raise HTTPException(status_code=404, detail="API key not found")

    key_obj.revoked_at = _dt.now(_tz.utc)
    await db.commit()
    return {"revoked": True, "id": str(key_obj.id)}


@router.post("/share-token")
async def create_share_token(user: User = Depends(get_current_user)):
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    token = jwt.encode(
        {"sub": str(user.id), "exp": expire, "type": "share"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"share_token": token, "expires_at": expire.date().isoformat()}


@router.get("/shared/{token}")
async def get_shared_dashboard(token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "share":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired share token")

    from sqlalchemy import select, desc
    from app.models.diagnostic import PDSLog, HQILog

    user_result = await db.execute(select(User).where(User.id == user_id))
    shared_user = user_result.scalar_one_or_none()
    if not shared_user:
        raise HTTPException(status_code=401, detail="User not found")

    pds_result = await db.execute(
        select(PDSLog).where(PDSLog.user_id == shared_user.id)
        .order_by(desc(PDSLog.recorded_date), desc(PDSLog.created_at)).limit(1)
    )
    pds = pds_result.scalar_one_or_none()

    hqi_result = await db.execute(
        select(HQILog).where(HQILog.user_id == shared_user.id)
        .order_by(desc(HQILog.recorded_date), desc(HQILog.created_at)).limit(1)
    )
    hqi = hqi_result.scalar_one_or_none()

    return {
        "username": shared_user.username,
        "pds": {
            "score": pds.pds_score,
            "tier": pds.tier,
            "date": str(pds.recorded_date),
        } if pds else None,
        "hqi": {
            "overall": hqi.overall_hqi,
            "site_scores": hqi.site_scores,
            "date": str(hqi.recorded_date),
        } if hqi else None,
    }
