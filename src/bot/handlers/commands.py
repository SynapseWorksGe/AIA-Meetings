"""Bot command handlers: /start, /help, /meetings, /meeting."""

import uuid

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.api.config import settings
from src.api.models.meeting import Meeting, MeetingStatus

router = Router()


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "<b>AIA-Meetings Bot</b>\n\n"
        "Я расшифровываю аудиозаписи встреч и генерирую:\n"
        "- Транскрипцию\n"
        "- Краткое саммари\n"
        "- Action items\n"
        "- Ключевые решения\n\n"
        "<b>Как пользоваться:</b>\n"
        "Отправьте мне аудиофайл или голосовое сообщение, и я обработаю его.\n\n"
        "<b>Команды:</b>\n"
        "/meetings — список последних встреч\n"
        "/meeting &lt;id&gt; — результат встречи\n"
        "/help — справка"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Справка</b>\n\n"
        "<b>Отправка аудио:</b>\n"
        "- Отправьте аудиофайл (mp3, wav, ogg, m4a)\n"
        "- Или запишите голосовое сообщение\n"
        "- Добавьте подпись к файлу — она станет названием встречи\n\n"
        "<b>Команды:</b>\n"
        "/meetings — 10 последних встреч\n"
        "/meeting &lt;id&gt; — подробный результат\n\n"
        "<b>Поддерживаемые форматы:</b> mp3, wav, ogg, m4a, webm, flac\n"
        "<b>Максимальный размер:</b> 50 МБ (ограничение Telegram)"
    )


@router.message(Command("meetings"))
async def cmd_meetings(message: Message):
    session_factory = _get_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(Meeting)
            .where(Meeting.source == "telegram", Meeting.title.isnot(None))
            .order_by(Meeting.created_at.desc())
            .limit(10)
        )
        meetings = result.scalars().all()

    if not meetings:
        await message.answer("У вас пока нет обработанных встреч. Отправьте мне аудиофайл!")
        return

    lines = ["<b>Последние встречи:</b>\n"]
    for m in meetings:
        status_icon = {
            MeetingStatus.uploading: "⬆️",
            MeetingStatus.transcribing: "🔄",
            MeetingStatus.summarizing: "🧠",
            MeetingStatus.done: "✅",
            MeetingStatus.error: "❌",
        }.get(m.status, "❓")

        short_id = str(m.id)[:8]
        date = m.created_at.strftime("%d.%m %H:%M")
        title = m.title or "Без названия"
        if len(title) > 40:
            title = title[:37] + "..."
        lines.append(f"{status_icon} <code>{short_id}</code> {title} ({date})")

    lines.append(f"\nДля деталей: /meeting &lt;id&gt;")
    await message.answer("\n".join(lines))


@router.message(Command("meeting"))
async def cmd_meeting(message: Message):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /meeting &lt;id&gt;\n\nID можно найти в /meetings")
        return

    meeting_id_str = args[1].strip()

    # Support both short (8 char) and full UUIDs
    session_factory = _get_session_factory()
    async with session_factory() as db:
        query = (
            select(Meeting)
            .options(selectinload(Meeting.transcript), selectinload(Meeting.summary))
            .where(Meeting.source == "telegram")
        )

        try:
            full_uuid = uuid.UUID(meeting_id_str)
            query = query.where(Meeting.id == full_uuid)
        except ValueError:
            # Short ID — search by prefix
            query = query.where(Meeting.id.cast(String).startswith(meeting_id_str))

        result = await db.execute(query)
        meeting = result.scalar_one_or_none()

    if not meeting:
        await message.answer("Встреча не найдена. Проверьте ID в /meetings")
        return

    await _send_meeting_result(message, meeting)


async def _send_meeting_result(message: Message, meeting: Meeting):
    """Format and send meeting result."""
    from src.bot.formatters import format_meeting_result

    text = format_meeting_result(meeting)

    # Telegram message limit is 4096 chars
    if len(text) <= 4096:
        await message.answer(text)
    else:
        # Send in chunks
        chunks = _split_text(text, 4096)
        for chunk in chunks:
            await message.answer(chunk)


def _split_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks respecting line breaks."""
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
