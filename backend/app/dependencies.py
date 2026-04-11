import hashlib
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_api_key(plaintext: str) -> str:
    """Hash a plaintext API key for storage + lookup."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        # Reject refresh tokens or share tokens presented as access tokens.
        token_type = payload.get("type", "access")
        if token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_user_via_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate via a long-lived HealthKit API key. Used by the iPhone
    Shortcut endpoint so morning check-ins can fire from Shortcuts (which
    can't do OAuth/JWT flows). Keys are stored as SHA-256 hashes — the
    plaintext is only ever shown once, at creation time.
    """
    from app.models.user import User, HealthKitApiKey

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked API key",
    )

    key_hash = hash_api_key(x_api_key.strip())
    key_row = await db.execute(
        select(HealthKitApiKey).where(
            HealthKitApiKey.api_key_hash == key_hash,
            HealthKitApiKey.revoked_at.is_(None),
        )
    )
    key_obj = key_row.scalar_one_or_none()
    if not key_obj:
        raise unauthorized

    user_row = await db.execute(select(User).where(User.id == key_obj.user_id))
    user = user_row.scalar_one_or_none()
    if not user or not user.is_active:
        raise unauthorized

    # Update last_used_at (fire-and-forget; commit will happen at request end)
    key_obj.last_used_at = datetime.now(timezone.utc)
    return user
