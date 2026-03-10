"""API key management routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.api_key import create_api_key
from src.api.database import get_db
from src.api.models.schemas import ApiKeyCreateResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/keys", response_model=ApiKeyCreateResponse)
async def create_new_api_key(
    name: str = "default",
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. Store it securely — it won't be shown again."""
    raw_key, key_id = await create_api_key(db, name)
    return ApiKeyCreateResponse(
        api_key=raw_key,
        name=name,
        message="Store this API key securely. It will not be shown again.",
    )
