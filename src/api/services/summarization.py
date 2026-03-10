"""Claude API integration for meeting summarization."""

import json

import anthropic

from src.api.config import settings

SUMMARIZE_PROMPT = """\
Ты — ассистент для анализа расшифровок деловых встреч. Проанализируй транскрипцию встречи и верни структурированный результат.

Транскрипция встречи:
---
{transcript}
---

Верни результат строго в формате JSON (без markdown, без ```):
{{
  "summary": "Краткое содержание встречи (2-5 предложений)",
  "action_items": [
    {{
      "task": "Описание задачи",
      "assignee": "Имя ответственного (или null если не указан)",
      "deadline": "Дедлайн (или null если не указан)"
    }}
  ],
  "key_decisions": [
    {{
      "decision": "Принятое решение",
      "context": "Краткий контекст решения"
    }}
  ],
  "participants": ["Имя1", "Имя2"]
}}

Правила:
- Если участники не называют имена, оставь participants пустым
- Извлекай только явно озвученные action items и решения
- Пиши на языке оригинала транскрипции
"""


async def summarize_transcript(transcript_text: str) -> dict:
    """Summarize a meeting transcript using Claude API."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": SUMMARIZE_PROMPT.format(transcript=transcript_text),
            }
        ],
    )

    response_text = message.content[0].text

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(response_text[start:end])
        else:
            result = {
                "summary": response_text,
                "action_items": [],
                "key_decisions": [],
                "participants": [],
            }

    return {
        "summary_text": result.get("summary", ""),
        "action_items": result.get("action_items", []),
        "key_decisions": result.get("key_decisions", []),
        "participants": result.get("participants", []),
    }
