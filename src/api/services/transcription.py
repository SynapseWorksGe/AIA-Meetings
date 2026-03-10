"""Yandex SpeechKit integration for speech-to-text."""

import base64
import logging
import os
import time

import httpx

from src.api.config import settings

logger = logging.getLogger(__name__)

# Yandex SpeechKit async recognition API
RECOGNIZE_URL = "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize"
OPERATION_URL = "https://operation.api.cloud.yandex.net/operations/{operation_id}"

# Map file extensions to Yandex SpeechKit audioEncoding values
_EXT_TO_ENCODING = {
    ".ogg": "OGG_OPUS",
    ".opus": "OGG_OPUS",
    ".mp3": "MP3",
    ".wav": "LINEAR16_PCM",
    ".flac": "LINEAR16_PCM",
    ".m4a": "MP3",
    ".webm": "OGG_OPUS",
    ".mp4": "MP3",
}


def _detect_encoding(file_path: str) -> str:
    """Detect audioEncoding from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    encoding = _EXT_TO_ENCODING.get(ext, "OGG_OPUS")
    logger.info("File %s -> audioEncoding=%s", ext, encoding)
    return encoding


async def start_recognition(file_path: str, language: str = "ru-RU") -> str:
    """Start async recognition and return operation ID."""
    from pathlib import Path

    if not settings.yandex_api_key:
        raise RuntimeError("YANDEX_API_KEY не задан в .env")
    if not settings.yandex_folder_id:
        raise RuntimeError("YANDEX_FOLDER_ID не задан в .env")

    file_data = Path(file_path).read_bytes()
    file_size_mb = len(file_data) / (1024 * 1024)
    logger.info("Audio file size: %.2f MB (%s)", file_size_mb, file_path)

    if file_size_mb > 50:
        raise RuntimeError(f"Файл слишком большой ({file_size_mb:.1f} МБ). Максимум 50 МБ.")

    audio_content = base64.b64encode(file_data).decode()
    audio_encoding = _detect_encoding(file_path)

    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "config": {
            "specification": {
                "languageCode": language,
                "model": "general",
                "audioEncoding": audio_encoding,
                "rawResults": True,
            },
            "folderId": settings.yandex_folder_id,
        },
        "audio": {
            "content": audio_content,
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(RECOGNIZE_URL, headers=headers, json=body)
        if response.status_code != 200:
            logger.error(
                "Yandex SpeechKit error %s: %s",
                response.status_code,
                response.text,
            )
            raise RuntimeError(
                f"Yandex SpeechKit вернул {response.status_code}: {response.text[:300]}"
            )
        result = response.json()

    operation_id = result.get("id")
    if not operation_id:
        raise RuntimeError(f"Failed to start recognition: {result}")

    return operation_id


async def poll_operation(operation_id: str, max_wait: int = 600) -> dict:
    """Poll operation until it's done. Returns the result."""
    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
    }
    url = OPERATION_URL.format(operation_id=operation_id)

    start_time = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.time() - start_time < max_wait:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()

            if result.get("done"):
                if "error" in result:
                    raise RuntimeError(f"Recognition failed: {result['error']}")
                return result.get("response", {})

            await _async_sleep(5)

    raise TimeoutError(f"Recognition did not complete within {max_wait}s")


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def parse_recognition_result(response: dict) -> tuple[str, list[dict]]:
    """Parse Yandex SpeechKit response into full_text and segments."""
    chunks = response.get("chunks", [])
    segments = []
    texts = []

    for chunk in chunks:
        alternatives = chunk.get("alternatives", [])
        if not alternatives:
            continue

        best = alternatives[0]
        text = best.get("text", "")
        texts.append(text)

        words = best.get("words", [])
        start_time = None
        end_time = None
        if words:
            start_time = _duration_to_seconds(words[0].get("startTime", "0s"))
            end_time = _duration_to_seconds(words[-1].get("endTime", "0s"))

        segments.append({
            "text": text,
            "start": start_time,
            "end": end_time,
            "channel": chunk.get("channelTag", "0"),
        })

    full_text = " ".join(texts)
    return full_text, segments


def _duration_to_seconds(duration_str: str) -> float:
    """Convert Yandex duration string (e.g., '1.500s') to float seconds."""
    if isinstance(duration_str, str) and duration_str.endswith("s"):
        return float(duration_str[:-1])
    return float(duration_str)


async def transcribe(file_path: str, language: str = "ru-RU") -> tuple[str, list[dict]]:
    """Full transcription pipeline: upload → recognize → parse."""
    operation_id = await start_recognition(file_path, language)
    response = await poll_operation(operation_id)
    return parse_recognition_result(response)
