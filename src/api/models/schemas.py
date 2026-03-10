import uuid
from datetime import datetime

from pydantic import BaseModel


# --- Request schemas ---


class MeetingUploadResponse(BaseModel):
    meeting_id: uuid.UUID
    status: str
    message: str


# --- Response schemas ---


class TranscriptResponse(BaseModel):
    full_text: str
    word_count: int
    segments: list[dict] | None = None

    model_config = {"from_attributes": True}


class ActionItem(BaseModel):
    task: str
    assignee: str | None = None
    deadline: str | None = None


class KeyDecision(BaseModel):
    decision: str
    context: str | None = None


class SummaryResponse(BaseModel):
    summary_text: str
    action_items: list[ActionItem] | None = None
    key_decisions: list[KeyDecision] | None = None
    participants: list[str] | None = None
    model_used: str

    model_config = {"from_attributes": True}


class MeetingResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    status: str
    error_message: str | None = None
    audio_duration_sec: int | None = None
    language: str
    source: str
    created_at: datetime
    updated_at: datetime
    transcript: TranscriptResponse | None = None
    summary: SummaryResponse | None = None

    model_config = {"from_attributes": True}


class MeetingListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    status: str
    audio_duration_sec: int | None = None
    language: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MeetingListResponse(BaseModel):
    meetings: list[MeetingListItem]
    total: int


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    name: str
    message: str
