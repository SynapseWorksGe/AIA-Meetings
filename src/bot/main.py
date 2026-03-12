"""Telegram bot entry point."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

import sqlalchemy as sa

from src.api.config import settings
from src.api.database import engine
from src.api.models.meeting import Base
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.handlers.audio import router as audio_router
from src.bot.handlers.commands import router as commands_router
from src.bot.handlers.settings import router as settings_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main():
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        return

    # Ensure all tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns that may be missing in existing tables
        for col_name, col_type in [
            ("yandex_api_key", "VARCHAR(500)"),
            ("yandex_folder_id", "VARCHAR(100)"),
        ]:
            try:
                await conn.execute(
                    sa.text(f"ALTER TABLE user_settings ADD COLUMN {col_name} {col_type}")
                )
                logger.info("Added column user_settings.%s", col_name)
            except Exception:
                pass  # column already exists
    logger.info("Database tables ensured")

    # Use local Telegram Bot API server if configured (removes 20 MB file limit)
    session = None
    if settings.telegram_bot_api_url:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(settings.telegram_bot_api_url)
        )
        logger.info("Using local Bot API server: %s", settings.telegram_bot_api_url)
    else:
        logger.warning(
            "TELEGRAM_BOT_API_URL not set — using official API (20 MB file limit). "
            "Set TELEGRAM_BOT_API_URL for large file support."
        )

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(commands_router)
    dp.include_router(settings_router)
    dp.include_router(audio_router)

    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
