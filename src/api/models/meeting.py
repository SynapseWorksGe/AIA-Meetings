import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AIProvider(str, enum.Enum):
    anthropic = "anthropic"
    openai = "openai"


AVAILABLE_MODELS = {
    "claude-sonnet-4": {"provider": AIProvider.anthropic, "model_id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4"},
    "claude-haiku-4": {"provider": AIProvider.anthropic, "model_id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5"},
    "gpt-4o": {"provider": AIProvider.openai, "model_id": "gpt-4o", "label": "GPT-4o"},
    "gpt-4o-mini": {"provider": AIProvider.openai, "model_id": "gpt-4o-mini", "label": "GPT-4o mini"},
}


class MeetingStatus(str, enum.Enum):
    uploading = "uploading"
    transcribing = "transcribing"
    summarizing = "summarizing"
    done = "done"
    error = "error"


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="default")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    meetings: Mapped[list["Meeting"]] = relationship(back_populates="api_key")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus), default=MeetingStatus.uploading)
    error_message: Mapped[str | None] = mapped_column(Text)
    audio_file_path: Mapped[str | None] = mapped_column(String(1000))
    audio_duration_sec: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(10), default="ru")
    source: Mapped[str] = mapped_column(String(50), default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("api_keys.id"))

    api_key: Mapped[ApiKey | None] = relationship(back_populates="meetings")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="meeting", uselist=False)
    summary: Mapped["Summary | None"] = relationship(back_populates="meeting", uselist=False)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), unique=True)
    full_text: Mapped[str] = mapped_column(Text, default="")
    segments: Mapped[dict | None] = mapped_column(JSONB)
    word_count: Mapped[int] = mapped_column(Integer, default=0)

    meeting: Mapped[Meeting] = relationship(back_populates="transcript")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), unique=True)
    summary_text: Mapped[str] = mapped_column(Text, default="")
    action_items: Mapped[list | None] = mapped_column(JSONB)
    key_decisions: Mapped[list | None] = mapped_column(JSONB)
    participants: Mapped[list | None] = mapped_column(JSONB)
    model_used: Mapped[str] = mapped_column(String(100), default="claude-sonnet-4-6")
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1")

    meeting: Mapped[Meeting] = relationship(back_populates="summary")


class UserSettings(Base):
    __tablename__ = "user_settings"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    selected_model: Mapped[str] = mapped_column(String(50), default="claude-sonnet-4")
    anthropic_api_key: Mapped[str | None] = mapped_column(String(500))
    openai_api_key: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
