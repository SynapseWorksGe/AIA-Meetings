"""Meeting API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth.api_key import get_current_api_key
from src.api.database import get_db
from src.api.models.meeting import ApiKey, Meeting, MeetingStatus, Summary, Transcript
from src.api.models.schemas import (
    MeetingListItem,
    MeetingListResponse,
    MeetingResponse,
    MeetingUploadResponse,
)
from src.api.services.storage import save_upload
from src.api.tasks.processing import process_meeting_task

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@router.post("/upload", response_model=MeetingUploadResponse, status_code=202)
async def upload_meeting(
    file: UploadFile,
    title: str | None = None,
    language: str = "ru",
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Upload an audio file for transcription and summarization."""
    try:
        file_path, original_name = await save_upload(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    meeting = Meeting(
        title=title or original_name,
        status=MeetingStatus.uploading,
        audio_file_path=file_path,
        language=language,
        source="api",
        api_key_id=api_key.id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    # Dispatch async processing
    process_meeting_task.delay(str(meeting.id))

    return MeetingUploadResponse(
        meeting_id=meeting.id,
        status=meeting.status.value,
        message="File uploaded. Processing started.",
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Get meeting details, transcript, and summary."""
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.transcript), selectinload(Meeting.summary))
        .where(Meeting.id == meeting_id, Meeting.api_key_id == api_key.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """List meetings for the current API key."""
    query = (
        select(Meeting)
        .where(Meeting.api_key_id == api_key.id)
        .order_by(Meeting.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    meetings = result.scalars().all()

    count_result = await db.execute(select(func.count(Meeting.id)).where(Meeting.api_key_id == api_key.id))
    total = count_result.scalar() or 0

    return MeetingListResponse(meetings=meetings, total=total)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Delete a meeting and its associated data."""
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.transcript), selectinload(Meeting.summary))
        .where(Meeting.id == meeting_id, Meeting.api_key_id == api_key.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Clean up audio file
    if meeting.audio_file_path:
        from src.api.services.storage import delete_file

        delete_file(meeting.audio_file_path)

    if meeting.transcript:
        await db.delete(meeting.transcript)
    if meeting.summary:
        await db.delete(meeting.summary)
    await db.delete(meeting)
    await db.commit()


@router.post("/{meeting_id}/resummarize", response_model=MeetingUploadResponse)
async def resummarize_meeting(
    meeting_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    """Re-generate summary for an already transcribed meeting."""
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.transcript), selectinload(Meeting.summary))
        .where(Meeting.id == meeting_id, Meeting.api_key_id == api_key.id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="Meeting has no transcript yet")

    # Remove old summary if exists
    if meeting.summary:
        await db.delete(meeting.summary)

    meeting.status = MeetingStatus.summarizing
    await db.commit()

    # Re-run just summarization (will be handled in a simplified task)
    process_meeting_task.delay(str(meeting.id))

    return MeetingUploadResponse(
        meeting_id=meeting.id,
        status=meeting.status.value,
        message="Re-summarization started.",
    )
