import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from src.api.config import settings

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".flac", ".mp4"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


def get_storage_path() -> Path:
    path = Path(settings.storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_audio_file(filename: str, content_type: str | None) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file format '{ext}'. Supported: {', '.join(ALLOWED_EXTENSIONS)}")
    return ext


async def save_upload(file: UploadFile) -> tuple[str, str]:
    """Save uploaded file and return (file_path, original_filename)."""
    ext = validate_audio_file(file.filename or "audio.mp3", file.content_type)
    file_id = uuid.uuid4().hex
    filename = f"{file_id}{ext}"
    file_path = get_storage_path() / filename

    size = 0
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                os.unlink(file_path)
                raise ValueError(f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB")
            await f.write(chunk)

    return str(file_path), file.filename or filename


def delete_file(file_path: str) -> None:
    try:
        os.unlink(file_path)
    except FileNotFoundError:
        pass
