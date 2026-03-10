"""Webhook management routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.api_key import get_current_api_key
from src.api.database import get_db
from src.api.models.meeting import ApiKey
from src.api.models.webhook import Webhook

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = ["meeting.completed", "meeting.error"]


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


class WebhookListResponse(BaseModel):
    webhooks: list[WebhookResponse]


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Register a webhook URL for event notifications."""
    valid_events = {"meeting.completed", "meeting.error"}
    invalid = set(body.events) - valid_events
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid events: {invalid}. Valid: {valid_events}")

    webhook = Webhook(
        api_key_id=api_key.id,
        url=body.url,
        events=body.events,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """List registered webhooks."""
    result = await db.execute(
        select(Webhook).where(Webhook.api_key_id == api_key.id, Webhook.is_active.is_(True))
    )
    webhooks = result.scalars().all()
    return WebhookListResponse(webhooks=webhooks)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Delete a webhook."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == api_key.id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()
