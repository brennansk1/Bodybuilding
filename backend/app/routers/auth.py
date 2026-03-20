import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
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
