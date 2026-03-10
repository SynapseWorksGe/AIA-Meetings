"""Format meeting results for Telegram messages."""

from src.api.models.meeting import Meeting


def format_meeting_result(meeting: Meeting) -> str:
    """Format a complete meeting result as a Telegram HTML message."""
    parts = []

    title = meeting.title or "Без названия"
    date = meeting.created_at.strftime("%d.%m.%Y %H:%M")
    parts.append(f"<b>📋 {title}</b>")
    parts.append(f"<i>{date}</i>")
    parts.append("")

    if meeting.status.value == "error":
        parts.append(f"❌ <b>Ошибка:</b> {meeting.error_message or 'Неизвестная ошибка'}")
        return "\n".join(parts)

    if meeting.status.value != "done":
        status_text = {
            "uploading": "Загрузка...",
            "transcribing": "Транскрибирую...",
            "summarizing": "Генерирую саммари...",
        }.get(meeting.status.value, meeting.status.value)
        parts.append(f"⏳ <b>Статус:</b> {status_text}")
        return "\n".join(parts)

    # Summary
    if meeting.summary:
        s = meeting.summary
        if s.summary_text:
            parts.append(f"<b>📝 Саммари:</b>")
            parts.append(s.summary_text)
            parts.append("")

        # Participants
        if s.participants:
            names = ", ".join(s.participants)
            parts.append(f"<b>👥 Участники:</b> {names}")
            parts.append("")

        # Action items
        if s.action_items:
            parts.append("<b>✅ Action Items:</b>")
            for i, item in enumerate(s.action_items, 1):
                task = item.get("task", "")
                assignee = item.get("assignee")
                deadline = item.get("deadline")
                line = f"{i}. {task}"
                details = []
                if assignee:
                    details.append(assignee)
                if deadline:
                    details.append(f"до {deadline}")
                if details:
                    line += f" ({', '.join(details)})"
                parts.append(line)
            parts.append("")

        # Key decisions
        if s.key_decisions:
            parts.append("<b>🔑 Ключевые решения:</b>")
            for item in s.key_decisions:
                decision = item.get("decision", "")
                context = item.get("context")
                line = f"• {decision}"
                if context:
                    line += f"\n  <i>{context}</i>"
                parts.append(line)
            parts.append("")

    # Transcript stats
    if meeting.transcript:
        word_count = meeting.transcript.word_count
        parts.append(f"<b>📄 Транскрипция:</b> {word_count} слов")
        short_id = str(meeting.id)[:8]
        parts.append(f"<code>/meeting {short_id}</code> — полный текст")

    return "\n".join(parts)


def format_transcript_text(meeting: Meeting) -> str:
    """Format just the transcript text."""
    if not meeting.transcript:
        return "Транскрипция недоступна."

    parts = [
        f"<b>📄 Транскрипция: {meeting.title or 'Без названия'}</b>",
        "",
        meeting.transcript.full_text,
    ]
    return "\n".join(parts)
