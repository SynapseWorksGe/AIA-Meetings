"""AI API integration for meeting summarization (Anthropic / OpenAI)."""

import json
import logging

import anthropic
import httpx

from src.api.config import settings
from src.api.models.meeting import AVAILABLE_MODELS, AIProvider

logger = logging.getLogger(__name__)

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


async def _call_anthropic(transcript_text: str, model_id: str, api_key: str) -> str:
    """Call Anthropic Claude API."""
    http_client = None
    if settings.anthropic_proxy_url:
        http_client = httpx.AsyncClient(
            proxy=settings.anthropic_proxy_url,
            timeout=httpx.Timeout(600.0, connect=30.0),
        )
    client = anthropic.AsyncAnthropic(
        api_key=api_key,
        http_client=http_client,
    )

    message = await client.messages.create(
        model=model_id,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": SUMMARIZE_PROMPT.format(transcript=transcript_text),
            }
        ],
    )
    return message.content[0].text


async def _call_openai(transcript_text: str, model_id: str, api_key: str) -> str:
    """Call OpenAI API via httpx (no SDK dependency needed)."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": SUMMARIZE_PROMPT.format(transcript=transcript_text),
                    }
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _parse_response(response_text: str) -> dict:
    """Parse JSON from model response."""
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
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
    return result


async def summarize_transcript(
    transcript_text: str,
    model_key: str = "claude-sonnet-4",
    user_anthropic_key: str | None = None,
    user_openai_key: str | None = None,
) -> dict:
    """Summarize a meeting transcript using the selected AI model."""
    model_info = AVAILABLE_MODELS.get(model_key)
    if not model_info:
        model_info = AVAILABLE_MODELS["claude-sonnet-4"]
        model_key = "claude-sonnet-4"

    provider = model_info["provider"]
    model_id = model_info["model_id"]

    if provider == AIProvider.anthropic:
        api_key = user_anthropic_key or settings.anthropic_api_key
        if not api_key:
            raise ValueError("Anthropic API key not configured. Use /settings to set it.")
        response_text = await _call_anthropic(transcript_text, model_id, api_key)
    elif provider == AIProvider.openai:
        api_key = user_openai_key
        if not api_key:
            raise ValueError("OpenAI API key not set. Use /settings to add your key.")
        response_text = await _call_openai(transcript_text, model_id, api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    result = _parse_response(response_text)

    return {
        "summary_text": result.get("summary", ""),
        "action_items": result.get("action_items", []),
        "key_decisions": result.get("key_decisions", []),
        "participants": result.get("participants", []),
        "model_used": model_id,
    }
