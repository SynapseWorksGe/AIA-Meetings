"""Webhook notification service."""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models.meeting import Meeting
from src.api.models.webhook import Webhook

logger = logging.getLogger(__name__)


async def notify_webhooks(db: AsyncSession, meeting: Meeting, event: str):
    """Send webhook notifications for a meeting event."""
    if not meeting.api_key_id:
        return

    result = await db.execute(
        select(Webhook).where(
            Webhook.api_key_id == meeting.api_key_id,
            Webhook.is_active.is_(True),
        )
    )
    webhooks = result.scalars().all()

    for webhook in webhooks:
        if event not in (webhook.events or []):
            continue

        payload = {
            "event": event,
            "meeting_id": str(meeting.id),
            "status": meeting.status.value,
            "title": meeting.title,
        }

        if event == "meeting.error" and meeting.error_message:
            payload["error"] = meeting.error_message

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook.url, json=payload)
                logger.info(f"Webhook {webhook.id} -> {webhook.url}: {response.status_code}")
        except Exception as e:
            logger.warning(f"Webhook {webhook.id} failed: {e}")
