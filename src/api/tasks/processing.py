"""Celery tasks for meeting processing pipeline."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.celery_app import celery_app
from src.api.config import settings
from src.api.models.meeting import Meeting, MeetingStatus, Summary, Transcript

logger = logging.getLogger(__name__)


def _get_async_session() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _run_async(coro):
    """Run an async coroutine in a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _process_meeting(meeting_id: str) -> None:
    from src.api.services.summarization import summarize_transcript
    from src.api.services.transcription import transcribe

    session_factory = _get_async_session()

    async with session_factory() as db:
        result = await db.execute(select(Meeting).where(Meeting.id == uuid.UUID(meeting_id)))
        meeting = result.scalar_one_or_none()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found")
            return

        try:
            # Step 1: Transcription
            meeting.status = MeetingStatus.transcribing
            await db.commit()

            lang_code = f"{meeting.language}-{meeting.language.upper()}" if len(meeting.language) == 2 else meeting.language
            full_text, segments = await transcribe(meeting.audio_file_path, lang_code)

            transcript = Transcript(
                meeting_id=meeting.id,
                full_text=full_text,
                segments=segments,
                word_count=len(full_text.split()),
            )
            db.add(transcript)
            await db.commit()

            # Step 2: Summarization
            meeting.status = MeetingStatus.summarizing
            await db.commit()

            summary_data = await summarize_transcript(full_text)

            summary = Summary(
                meeting_id=meeting.id,
                summary_text=summary_data["summary_text"],
                action_items=summary_data["action_items"],
                key_decisions=summary_data["key_decisions"],
                participants=summary_data["participants"],
            )
            db.add(summary)

            meeting.status = MeetingStatus.done
            await db.commit()

            # Send webhook notifications
            try:
                from src.api.services.notifications import notify_webhooks

                await notify_webhooks(db, meeting, "meeting.completed")
            except Exception:
                logger.warning(f"Failed to send webhook for meeting {meeting_id}", exc_info=True)

            logger.info(f"Meeting {meeting_id} processed successfully")

        except Exception as e:
            meeting.status = MeetingStatus.error
            meeting.error_message = str(e)[:2000]
            await db.commit()

            try:
                from src.api.services.notifications import notify_webhooks

                await notify_webhooks(db, meeting, "meeting.error")
            except Exception:
                logger.warning(f"Failed to send error webhook for meeting {meeting_id}", exc_info=True)
            logger.exception(f"Failed to process meeting {meeting_id}")
            raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_meeting_task(self, meeting_id: str) -> dict:
    """Process a meeting: transcribe → summarize."""
    try:
        _run_async(_process_meeting(meeting_id))
        return {"meeting_id": meeting_id, "status": "done"}
    except Exception as exc:
        logger.exception(f"Task failed for meeting {meeting_id}")
        raise self.retry(exc=exc)
