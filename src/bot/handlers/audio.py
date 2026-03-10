"""Handler for audio files and voice messages."""

import asyncio
import logging
import os
import tempfile
import uuid

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.api.config import settings
from src.api.models.meeting import AVAILABLE_MODELS, Meeting, MeetingStatus, Summary, Transcript, UserSettings
from src.api.services.summarization import summarize_transcript
from src.api.services.transcription import transcribe

logger = logging.getLogger(__name__)
router = Router()


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot):
    """Handle voice messages."""
    voice = message.voice
    title = message.caption or f"Голосовое {message.date.strftime('%d.%m.%Y %H:%M')}"

    status_msg = await message.answer("⏳ Получил голосовое сообщение. Скачиваю...")

    file = await bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await bot.download_file(file.file_path, tmp)
        tmp_path = tmp.name

    await _process_audio(message, bot, status_msg, tmp_path, title, voice.duration)


@router.message(F.audio)
async def handle_audio(message: Message, bot: Bot):
    """Handle audio file uploads."""
    audio = message.audio
    ext = os.path.splitext(audio.file_name or "audio.mp3")[1] or ".mp3"
    title = message.caption or audio.file_name or f"Аудио {message.date.strftime('%d.%m.%Y %H:%M')}"

    status_msg = await message.answer(f"⏳ Получил файл <b>{audio.file_name}</b>. Скачиваю...")

    file = await bot.get_file(audio.file_id)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        await bot.download_file(file.file_path, tmp)
        tmp_path = tmp.name

    await _process_audio(message, bot, status_msg, tmp_path, title, audio.duration)


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Handle document uploads (audio files sent as documents)."""
    doc = message.document
    if not doc.file_name:
        return

    ext = os.path.splitext(doc.file_name)[1].lower()
    allowed = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".flac", ".mp4"}
    if ext not in allowed:
        return  # Not an audio file, ignore silently

    title = message.caption or doc.file_name

    status_msg = await message.answer(f"⏳ Получил файл <b>{doc.file_name}</b>. Скачиваю...")

    file = await bot.get_file(doc.file_id)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        await bot.download_file(file.file_path, tmp)
        tmp_path = tmp.name

    await _process_audio(message, bot, status_msg, tmp_path, title, None)


async def _process_audio(
    message: Message,
    bot: Bot,
    status_msg: Message,
    file_path: str,
    title: str,
    duration: int | None,
):
    """Process audio file: save to DB, transcribe, summarize, send result."""
    session_factory = _get_session_factory()

    # Save meeting record
    async with session_factory() as db:
        meeting = Meeting(
            title=title,
            status=MeetingStatus.uploading,
            audio_file_path=file_path,
            audio_duration_sec=duration,
            language="ru",
            source="telegram",
        )
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)
        meeting_id = meeting.id

    try:
        # Step 1: Transcription
        await _update_status(status_msg, "🔄 Транскрибирую аудио... Это может занять несколько минут.")
        async with session_factory() as db:
            meeting = await _get_meeting(db, meeting_id)
            meeting.status = MeetingStatus.transcribing
            await db.commit()

        full_text, segments = await transcribe(file_path, "ru-RU")

        async with session_factory() as db:
            transcript = Transcript(
                meeting_id=meeting_id,
                full_text=full_text,
                segments=segments,
                word_count=len(full_text.split()),
            )
            db.add(transcript)
            await db.commit()

        word_count = len(full_text.split())
        await _update_status(
            status_msg,
            f"📝 Транскрипция готова ({word_count} слов). Генерирую саммари..."
        )

        # Step 2: Summarization — load user settings
        async with session_factory() as db:
            meeting = await _get_meeting(db, meeting_id)
            meeting.status = MeetingStatus.summarizing
            await db.commit()

            result = await db.execute(
                select(UserSettings).where(
                    UserSettings.telegram_user_id == message.from_user.id
                )
            )
            user_settings = result.scalar_one_or_none()

        model_key = user_settings.selected_model if user_settings else "claude-sonnet-4"
        user_anthropic_key = user_settings.anthropic_api_key if user_settings else None
        user_openai_key = user_settings.openai_api_key if user_settings else None
        user_yandex_key = user_settings.yandex_api_key if user_settings else None
        user_yandex_folder_id = user_settings.yandex_folder_id if user_settings else None

        model_label = AVAILABLE_MODELS.get(model_key, {}).get("label", model_key)
        await _update_status(
            status_msg,
            f"🧠 Генерирую саммари ({model_label})..."
        )

        summary_data = await summarize_transcript(
            full_text,
            model_key=model_key,
            user_anthropic_key=user_anthropic_key,
            user_openai_key=user_openai_key,
            user_yandex_key=user_yandex_key,
            user_yandex_folder_id=user_yandex_folder_id,
        )

        async with session_factory() as db:
            summary = Summary(
                meeting_id=meeting_id,
                summary_text=summary_data["summary_text"],
                action_items=summary_data["action_items"],
                key_decisions=summary_data["key_decisions"],
                participants=summary_data["participants"],
                model_used=summary_data.get("model_used", "unknown"),
            )
            db.add(summary)
            meeting = await _get_meeting(db, meeting_id)
            meeting.status = MeetingStatus.done
            await db.commit()

        # Send result
        await _update_status(status_msg, "✅ Обработка завершена!")

        async with session_factory() as db:
            result = await db.execute(
                select(Meeting)
                .options(selectinload(Meeting.transcript), selectinload(Meeting.summary))
                .where(Meeting.id == meeting_id)
            )
            meeting = result.scalar_one()

        from src.bot.formatters import format_meeting_result

        text = format_meeting_result(meeting)
        if len(text) <= 4096:
            await message.answer(text)
        else:
            chunks = _split_text(text, 4096)
            for chunk in chunks:
                await message.answer(chunk)

    except Exception as e:
        logger.exception(f"Failed to process meeting {meeting_id}")
        async with session_factory() as db:
            meeting = await _get_meeting(db, meeting_id)
            meeting.status = MeetingStatus.error
            meeting.error_message = str(e)[:2000]
            await db.commit()

        await _update_status(status_msg, f"❌ Ошибка обработки: {str(e)[:200]}")

    finally:
        # Clean up temp file
        try:
            os.unlink(file_path)
        except OSError:
            pass


async def _get_meeting(db: AsyncSession, meeting_id: uuid.UUID) -> Meeting:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    return result.scalar_one()


async def _update_status(status_msg: Message, text: str):
    """Edit status message, ignore errors if message hasn't changed."""
    try:
        await status_msg.edit_text(text)
    except Exception:
        pass


def _split_text(text: str, max_len: int) -> list[str]:
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks
