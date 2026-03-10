import hashlib
import secrets
import uuid

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.database import get_db
from src.api.models.meeting import ApiKey

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    return f"aia_{secrets.token_urlsafe(32)}"


async def get_current_api_key(
    api_key: str = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    key_hash = hash_api_key(api_key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)))
    db_key = result.scalar_one_or_none()
    if db_key is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return db_key


async def create_api_key(db: AsyncSession, name: str = "default") -> tuple[str, uuid.UUID]:
    raw_key = generate_api_key()
    db_key = ApiKey(key_hash=hash_api_key(raw_key), name=name)
    db.add(db_key)
    await db.commit()
    await db.refresh(db_key)
    return raw_key, db_key.id
