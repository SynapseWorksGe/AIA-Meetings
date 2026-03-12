"""Yandex SpeechKit integration for speech-to-text."""

import asyncio
import logging
import os
import tempfile
import time
import uuid

import httpx

from src.api.config import settings

logger = logging.getLogger(__name__)

# Yandex SpeechKit async recognition API
RECOGNIZE_URL = "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize"
OPERATION_URL = "https://operation.api.cloud.yandex.net/operations/{operation_id}"

# Yandex Object Storage
S3_ENDPOINT = "https://storage.yandexcloud.net"

# Map file extensions to Yandex SpeechKit audioEncoding values
_EXT_TO_ENCODING = {
    ".ogg": "OGG_OPUS",
    ".opus": "OGG_OPUS",
    ".mp3": "MP3",
    ".wav": "LINEAR16_PCM",
    ".flac": "LINEAR16_PCM",
}

# Formats that need conversion to OGG Opus before sending to SpeechKit
_NEEDS_CONVERSION = {".m4a", ".mp4", ".webm", ".aac", ".wma"}


async def _convert_to_ogg(file_path: str) -> str | None:
    """Convert audio file to OGG Opus using ffmpeg. Returns new path or None if not needed."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _NEEDS_CONVERSION:
        return None

    ogg_path = tempfile.mktemp(suffix=".ogg")
    cmd = [
        "ffmpeg", "-i", file_path,
        "-vn",                  # no video
        "-acodec", "libopus",   # Opus codec
        "-ac", "1",             # mono
        "-ar", "48000",         # 48kHz sample rate
        "-b:a", "64k",          # bitrate
        "-y",                   # overwrite
        ogg_path,
    ]

    logger.info("Converting %s -> OGG Opus: %s", ext, ogg_path)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("ffmpeg conversion failed: %s", stderr.decode()[-500:])
        try:
            os.unlink(ogg_path)
        except OSError:
            pass
        raise RuntimeError(f"Не удалось сконвертировать аудио ({ext}). Убедитесь, что ffmpeg установлен.")

    logger.info("Conversion complete: %s (%.2f MB)", ogg_path, os.path.getsize(ogg_path) / 1024 / 1024)
    return ogg_path


def _detect_encoding(file_path: str) -> str:
    """Detect audioEncoding from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    encoding = _EXT_TO_ENCODING.get(ext, "OGG_OPUS")
    logger.info("File %s -> audioEncoding=%s", ext, encoding)
    return encoding


async def _upload_to_s3(file_path: str) -> str:
    """Upload audio file to Yandex Object Storage and return the S3 URI."""
    import boto3
    from pathlib import Path

    if not settings.yandex_s3_access_key or not settings.yandex_s3_secret_key:
        raise RuntimeError("YANDEX_S3_ACCESS_KEY и YANDEX_S3_SECRET_KEY не заданы в .env")

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=settings.yandex_s3_access_key,
        aws_secret_access_key=settings.yandex_s3_secret_key,
        region_name="ru-central1",
    )

    ext = os.path.splitext(file_path)[1].lower()
    object_key = f"audio/{uuid.uuid4()}{ext}"

    file_data = Path(file_path).read_bytes()
    file_size_mb = len(file_data) / (1024 * 1024)
    logger.info("Uploading %.2f MB to s3://%s/%s", file_size_mb, settings.yandex_s3_bucket, object_key)

    if file_size_mb > 500:
        raise RuntimeError(f"Файл слишком большой ({file_size_mb:.1f} МБ). Максимум 500 МБ.")

    # Run synchronous boto3 upload in a thread pool
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: s3.put_object(
            Bucket=settings.yandex_s3_bucket,
            Key=object_key,
            Body=file_data,
        ),
    )

    uri = f"https://{settings.yandex_s3_bucket}.storage.yandexcloud.net/{object_key}"
    logger.info("Uploaded to %s", uri)
    return uri


async def _cleanup_s3(uri: str) -> None:
    """Delete audio file from S3 after processing."""
    try:
        import boto3

        # Extract bucket and key from URI
        # Format: https://bucket.storage.yandexcloud.net/key
        parts = uri.replace("https://", "").split(".storage.yandexcloud.net/", 1)
        if len(parts) != 2:
            return
        bucket, key = parts

        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=settings.yandex_s3_access_key,
            aws_secret_access_key=settings.yandex_s3_secret_key,
            region_name="ru-central1",
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: s3.delete_object(Bucket=bucket, Key=key),
        )
        logger.info("Cleaned up S3 object: %s", uri)
    except Exception:
        logger.warning("Failed to cleanup S3 object: %s", uri, exc_info=True)


async def start_recognition(file_path: str, language: str = "ru-RU") -> tuple[str, str]:
    """Start async recognition and return (operation_id, s3_uri)."""
    if not settings.yandex_api_key:
        raise RuntimeError("YANDEX_API_KEY не задан в .env")
    if not settings.yandex_folder_id:
        raise RuntimeError("YANDEX_FOLDER_ID не задан в .env")

    # Upload to Object Storage
    s3_uri = await _upload_to_s3(file_path)
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
            "uri": s3_uri,
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
            await _cleanup_s3(s3_uri)
            raise RuntimeError(
                f"Yandex SpeechKit вернул {response.status_code}: {response.text[:300]}"
            )
        result = response.json()

    operation_id = result.get("id")
    if not operation_id:
        await _cleanup_s3(s3_uri)
        raise RuntimeError(f"Failed to start recognition: {result}")

    return operation_id, s3_uri


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

            await asyncio.sleep(5)

    raise TimeoutError(f"Recognition did not complete within {max_wait}s")


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
    """Full transcription pipeline: convert (if needed) → upload to S3 → recognize → parse → cleanup."""
    converted_path = await _convert_to_ogg(file_path)
    actual_path = converted_path or file_path

    try:
        operation_id, s3_uri = await start_recognition(actual_path, language)
        try:
            response = await poll_operation(operation_id)
            return parse_recognition_result(response)
        finally:
            await _cleanup_s3(s3_uri)
    finally:
        if converted_path:
            try:
                os.unlink(converted_path)
            except OSError:
                pass
