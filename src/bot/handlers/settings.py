"""Handler for user settings: model selection and API key management."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.config import settings
from src.api.models.meeting import AVAILABLE_MODELS, AIProvider, UserSettings

logger = logging.getLogger(__name__)
router = Router()


class SettingsStates(StatesGroup):
    waiting_api_key = State()
    waiting_yandex_folder_id = State()


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _get_user_settings(db: AsyncSession, user_id: int) -> UserSettings | None:
    result = await db.execute(
        select(UserSettings).where(UserSettings.telegram_user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_or_create_settings(db: AsyncSession, user_id: int) -> UserSettings:
    us = await _get_user_settings(db, user_id)
    if not us:
        us = UserSettings(telegram_user_id=user_id)
        db.add(us)
        await db.commit()
        await db.refresh(us)
    return us


def _build_model_keyboard(current_model: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, info in AVAILABLE_MODELS.items():
        check = " ✓" if key == current_model else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{info['label']}{check}",
                callback_data=f"set_model:{key}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔑 Указать API-ключ", callback_data="set_api_key"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _settings_text(us: UserSettings) -> str:
    model_info = AVAILABLE_MODELS.get(us.selected_model, {})
    model_label = model_info.get("label", us.selected_model)
    provider = model_info.get("provider", AIProvider.anthropic)

    has_key = False
    if provider == AIProvider.anthropic:
        has_key = bool(us.anthropic_api_key or settings.anthropic_api_key)
    elif provider == AIProvider.openai:
        has_key = bool(us.openai_api_key)
    elif provider == AIProvider.yandex:
        yandex_key = us.yandex_api_key or settings.yandex_api_key
        yandex_folder = us.yandex_folder_id or settings.yandex_folder_id
        has_key = bool(yandex_key and yandex_folder)

    key_status = "✅ установлен" if has_key else "❌ не указан"

    extra = ""
    if provider == AIProvider.yandex and not has_key:
        extra = "\n⚠️ Для YandexGPT нужны API-ключ и Folder ID"

    return (
        "<b>⚙️ Настройки</b>\n\n"
        f"<b>Модель:</b> {model_label}\n"
        f"<b>API-ключ ({provider.value}):</b> {key_status}{extra}\n\n"
        "Выберите модель для суммаризации:"
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext):
    await state.clear()
    try:
        session_factory = _get_session_factory()
        async with session_factory() as db:
            us = await _get_or_create_settings(db, message.from_user.id)

        await message.answer(
            _settings_text(us),
            reply_markup=_build_model_keyboard(us.selected_model),
        )
    except Exception as e:
        logger.exception("Error in /settings handler")
        await message.answer(f"❌ Ошибка при загрузке настроек: {e}")


@router.callback_query(F.data.startswith("set_model:"))
async def on_model_selected(callback: CallbackQuery):
    model_key = callback.data.split(":", 1)[1]
    if model_key not in AVAILABLE_MODELS:
        await callback.answer("Неизвестная модель")
        return

    model_info = AVAILABLE_MODELS[model_key]
    session_factory = _get_session_factory()
    async with session_factory() as db:
        us = await _get_or_create_settings(db, callback.from_user.id)
        us.selected_model = model_key
        await db.commit()
        await db.refresh(us)

    # Check if API key is needed
    provider = model_info["provider"]
    needs_key = False
    if provider == AIProvider.anthropic and not us.anthropic_api_key and not settings.anthropic_api_key:
        needs_key = True
    elif provider == AIProvider.openai and not us.openai_api_key:
        needs_key = True
    elif provider == AIProvider.yandex:
        yandex_key = us.yandex_api_key or settings.yandex_api_key
        yandex_folder = us.yandex_folder_id or settings.yandex_folder_id
        if not yandex_key or not yandex_folder:
            needs_key = True

    await callback.message.edit_text(
        _settings_text(us),
        reply_markup=_build_model_keyboard(us.selected_model),
    )

    if needs_key:
        await callback.answer(
            f"⚠️ Для {model_info['label']} нужен API-ключ. Нажмите '🔑 Указать API-ключ'.",
            show_alert=True,
        )
    else:
        await callback.answer(f"Выбрана модель: {model_info['label']}")


@router.callback_query(F.data == "set_api_key")
async def on_set_api_key(callback: CallbackQuery, state: FSMContext):
    session_factory = _get_session_factory()
    async with session_factory() as db:
        us = await _get_or_create_settings(db, callback.from_user.id)

    model_info = AVAILABLE_MODELS.get(us.selected_model, {})
    provider = model_info.get("provider", AIProvider.anthropic)

    await state.set_state(SettingsStates.waiting_api_key)
    await state.update_data(provider=provider.value)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_api_key")]
    ])

    await callback.message.answer(
        f"🔑 Отправьте API-ключ для <b>{provider.value.title()}</b>.\n\n"
        "⚠️ Ключ будет сохранён и использован только для ваших запросов.\n"
        "Сообщение с ключом будет удалено после сохранения.",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_api_key")
async def on_cancel_api_key(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Ввод API-ключа отменён.")
    await callback.answer()


@router.message(SettingsStates.waiting_api_key)
async def on_api_key_received(message: Message, state: FSMContext):
    data = await state.get_data()
    provider = data.get("provider", "anthropic")
    api_key = message.text.strip()

    # Delete the message with the key for security
    try:
        await message.delete()
    except Exception:
        pass

    if not api_key or len(api_key) < 10:
        await message.answer("❌ Некорректный ключ. Попробуйте ещё раз или нажмите Отмена.")
        return

    session_factory = _get_session_factory()
    async with session_factory() as db:
        us = await _get_or_create_settings(db, message.from_user.id)
        if provider == "anthropic":
            us.anthropic_api_key = api_key
        elif provider == "openai":
            us.openai_api_key = api_key
        elif provider == "yandex":
            us.yandex_api_key = api_key
            await db.commit()
            # Ask for folder_id next
            await state.set_state(SettingsStates.waiting_yandex_folder_id)
            await message.answer(
                "✅ API-ключ Yandex сохранён!\n\n"
                "Теперь отправьте <b>Folder ID</b> вашего каталога в Yandex Cloud.\n"
                "Его можно найти в консоли: https://console.yandex.cloud/",
            )
            return
        await db.commit()
        await db.refresh(us)

    await state.clear()
    await message.answer(
        f"✅ API-ключ для <b>{provider.title()}</b> сохранён!\n\n"
        "Используйте /settings для просмотра настроек.",
    )


@router.message(SettingsStates.waiting_yandex_folder_id)
async def on_yandex_folder_received(message: Message, state: FSMContext):
    folder_id = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if not folder_id or len(folder_id) < 5:
        await message.answer("❌ Некорректный Folder ID. Попробуйте ещё раз.")
        return

    session_factory = _get_session_factory()
    async with session_factory() as db:
        us = await _get_or_create_settings(db, message.from_user.id)
        us.yandex_folder_id = folder_id
        await db.commit()

    await state.clear()
    await message.answer(
        "✅ Yandex Folder ID сохранён!\n\n"
        "Настройка YandexGPT завершена. Используйте /settings для просмотра.",
    )
