# AIA-Meetings

Сервис автоматической расшифровки встреч с генерацией саммари и action items.

## Возможности

- **Транскрипция** аудиозаписей встреч (Yandex SpeechKit)
- **AI-суммаризация** с извлечением action items и ключевых решений (Claude API)
- **Telegram-бот** для быстрой расшифровки голосовых и файлов
- **REST API** для интеграции с AI-агентами и другими сервисами
- **CLI** для macOS

## Быстрый старт

```bash
# Клонировать
git clone <repo-url>
cd AIA-Meetings

# Настроить окружение
cp .env.example .env
# Заполнить .env (API-ключи Yandex, Anthropic, Telegram)

# Запустить
docker compose up -d
```

## Документация

- [Архитектура](docs/ARCHITECTURE.md) — полное описание архитектуры, API, модели данных
