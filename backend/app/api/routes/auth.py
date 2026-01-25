from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DBSession, RequiredAPIKey
from app.core.security import generate_api_key, hash_api_key
from app.models.auth import APIKey
from app.schemas.auth import APIKeyCreate, APIKeyListResponse, APIKeyResponse

router = APIRouter()


@router.post("/keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    db: DBSession,
) -> APIKeyResponse:
    """Generate a new API key."""
    # Generate the key
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    # Create the database record
    api_key = APIKey(
        key_hash=key_hash,
        name=key_data.name,
    )
    db.add(api_key)
    await db.flush()

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,  # Only returned on creation
        created_at=api_key.created_at,
        last_used=api_key.last_used,
        is_active=api_key.is_active,
    )


@router.get("/keys", response_model=APIKeyListResponse)
async def list_api_keys(
    db: DBSession,
    current_key: RequiredAPIKey,
) -> APIKeyListResponse:
    """List all API keys (requires authentication)."""
    result = await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))
    keys = result.scalars().all()

    return APIKeyListResponse(
        keys=[
            APIKeyResponse(
                id=k.id,
                name=k.name,
                key=None,  # Never expose the key after creation
                created_at=k.created_at,
                last_used=k.last_used,
                is_active=k.is_active,
            )
            for k in keys
        ],
        total=len(keys),
    )


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    db: DBSession,
    current_key: RequiredAPIKey,
) -> None:
    """Revoke an API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key with ID {key_id} not found",
        )

    # Don't allow revoking your own key
    if api_key.id == current_key.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke your own API key",
        )

    api_key.is_active = False
