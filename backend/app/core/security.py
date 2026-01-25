import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import APIKey


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
    db: AsyncSession = None,
) -> APIKey | None:
    """Verify an API key and return the key record if valid."""
    if api_key is None:
        return None

    key_hash = hash_api_key(api_key)
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
        )
    )
    db_key = result.scalar_one_or_none()

    if db_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    # Update last used timestamp
    db_key.last_used = datetime.now(timezone.utc)
    await db.commit()

    return db_key


async def get_optional_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Get API key without requiring authentication."""
    return api_key
