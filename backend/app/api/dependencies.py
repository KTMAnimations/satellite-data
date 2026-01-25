from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import api_key_header, hash_api_key
from app.models.auth import APIKey
from sqlalchemy import select


# Database dependency
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_api_key(
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> APIKey | None:
    """Get the current API key if provided, or None for public endpoints."""
    if api_key is None:
        return None

    key_hash = hash_api_key(api_key)
    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)
    )
    db_key = result.scalar_one_or_none()

    if db_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    return db_key


async def require_api_key(
    api_key: APIKey | None = Depends(get_current_api_key),
) -> APIKey:
    """Require a valid API key for protected endpoints."""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


# Optional API key dependency
OptionalAPIKey = Annotated[APIKey | None, Depends(get_current_api_key)]

# Required API key dependency
RequiredAPIKey = Annotated[APIKey, Depends(require_api_key)]


# Pagination dependencies
class PaginationParams:
    """Common pagination parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


Pagination = Annotated[PaginationParams, Depends()]
