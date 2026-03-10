# AIA-Meetings: Сервис расшифровки встреч

## Обзор

Сервис для автоматической транскрипции аудиозаписей встреч с генерацией саммари, action items и ключевых решений. Доступен через Mac-приложение, Telegram-бот и REST API для интеграции с ИИ-агентами.

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| STT (Speech-to-Text) | Yandex SpeechKit |
| AI-обработка | Claude API (Anthropic) |
| База данных | PostgreSQL + SQLAlchemy |
| Очередь задач | Celery + Redis |
| Telegram-бот | aiogram 3 |
| Деплой | Docker Compose → VPS (рекомендация) |

## Архитектура

```
┌──────────────────────────────────────────────────────────┐
│                      КЛИЕНТЫ                             │
│                                                          │
│  ┌────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │  Mac App   │  │ Telegram Bot  │  │  AI Agent (API) │  │
│  │ (аудио)    │  │ (голос/файл)  │  │  (REST client)  │  │
│  └─────┬──────┘  └──────┬────────┘  └────────┬────────┘  │
└────────┼────────────────┼────────────────────┼───────────┘
         │                │                    │
         ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                    REST API (FastAPI)                     │
│                                                          │
│  POST /api/v1/meetings/upload     — загрузить аудио      │
│  GET  /api/v1/meetings/{id}       — статус/результат     │
│  GET  /api/v1/meetings            — список встреч        │
│  POST /api/v1/meetings/{id}/summarize — пересоздать саммари│
│  GET  /api/v1/meetings/{id}/transcript — текст           │
│  DELETE /api/v1/meetings/{id}     — удалить              │
│                                                          │
│  Auth: API Key (header X-API-Key)                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   ОБРАБОТКА (Pipeline)                    │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │ 1. Upload │───▶│ 2. Yandex    │───▶│ 3. Claude API  │  │
│  │ & Store   │    │ SpeechKit    │    │ Summarization  │  │
│  │ (S3/disk) │    │ (STT)        │    │                │  │
│  └──────────┘    └──────────────┘    └────────────────┘  │
│                                                          │
│  Оркестрация: Celery + Redis                             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  ХРАНЕНИЕ ДАННЫХ                         │
│                                                          │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │ PostgreSQL   │  │ Redis         │  │ File Storage │  │
│  │ (метаданные, │  │ (очередь,     │  │ (аудиофайлы) │  │
│  │  транскрипты, │  │  кэш,         │  │              │  │
│  │  саммари)    │  │  сессии)      │  │              │  │
│  └──────────────┘  └───────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Pipeline обработки встречи

```
Audio Upload ──▶ Validate ──▶ Store File ──▶ Celery Task
                  (format,       (disk/S3)      │
                   size)                        │
                                                ▼
                                        Yandex SpeechKit
                                        (async recognition)
                                                │
                                                ▼
                                        Save Transcript
                                                │
                                                ▼
                                        Claude API
                                        ├── Summary
                                        ├── Action Items
                                        ├── Key Decisions
                                        └── Participants
                                                │
                                                ▼
                                        Save Results
                                        + Notify Client
```

## Модель данных

```python
# meetings table
Meeting:
    id: UUID
    title: str                    # название (авто или ручное)
    status: enum                  # uploading | transcribing | summarizing | done | error
    audio_file_path: str          # путь к аудиофайлу
    audio_duration_sec: int       # длительность
    language: str                 # "ru" | "en" | auto
    created_at: datetime
    updated_at: datetime
    source: str                   # "api" | "telegram" | "mac"
    api_key_id: UUID (FK)

# transcripts table
Transcript:
    id: UUID
    meeting_id: UUID (FK)
    full_text: text               # полный текст
    segments: jsonb               # [{start, end, text, speaker}]
    word_count: int

# summaries table
Summary:
    id: UUID
    meeting_id: UUID (FK)
    summary_text: text            # краткое содержание
    action_items: jsonb           # [{task, assignee, deadline}]
    key_decisions: jsonb          # [{decision, context}]
    participants: jsonb           # [name, ...]
    model_used: str               # "claude-sonnet-4-6"
    prompt_version: str
```

## API Endpoints (детально)

### Upload Meeting
```
POST /api/v1/meetings/upload
Content-Type: multipart/form-data
X-API-Key: <key>

Body:
  file: <audio file> (mp3, wav, ogg, m4a — до 500MB)
  title: string (optional)
  language: string (optional, default: "ru")

Response 202:
{
  "meeting_id": "uuid",
  "status": "uploading",
  "estimated_duration_sec": null
}
```

### Get Meeting Result
```
GET /api/v1/meetings/{meeting_id}
X-API-Key: <key>

Response 200:
{
  "id": "uuid",
  "title": "Планёрка 10 марта",
  "status": "done",
  "audio_duration_sec": 3600,
  "transcript": {
    "full_text": "...",
    "word_count": 8500
  },
  "summary": {
    "text": "На встрече обсуждались...",
    "action_items": [
      {"task": "Подготовить отчёт", "assignee": "Иван", "deadline": "2026-03-15"}
    ],
    "key_decisions": [
      {"decision": "Переходим на новый стек", "context": "..."}
    ],
    "participants": ["Иван", "Мария", "Алексей"]
  },
  "created_at": "2026-03-10T14:30:00Z"
}
```

### Webhook / Polling
```
# Вариант 1: Polling
GET /api/v1/meetings/{id}/status → { "status": "transcribing", "progress": 65 }

# Вариант 2: Webhook (для AI-агента)
POST /api/v1/webhooks
{
  "url": "https://my-agent.com/callback",
  "events": ["meeting.completed", "meeting.error"]
}
```

## Telegram Bot

### Функционал
- Отправка голосового сообщения или аудиофайла → транскрипция + саммари
- Команды:
  - `/start` — регистрация, получение API-ключа
  - `/meetings` — список последних встреч
  - `/meeting <id>` — результат конкретной встречи
  - `/settings` — язык, формат вывода

### Сценарий
```
User: [отправляет аудиофайл]
Bot:  ⏳ Получил файл (45 мин). Начинаю обработку...
Bot:  📝 Транскрипция готова (12 мин)
Bot:  🔄 Генерирую саммари...
Bot:  ✅ Встреча обработана!

      📋 Саммари:
      На встрече обсуждалось...

      ✅ Action Items:
      1. Иван — подготовить отчёт (до 15.03)
      2. Мария — ревью кода (до 12.03)

      🔑 Ключевые решения:
      - Переходим на FastAPI
      - Релиз 1 апреля

      [Полный текст] [Скачать]
```

## Mac-приложение (Фаза 1: CLI-утилита)

На первом этапе — CLI-скрипт для macOS:

```bash
# Запись и отправка
aia-meetings record              # начать запись с микрофона
aia-meetings upload meeting.mp3  # отправить существующий файл
aia-meetings status <id>         # проверить статус
aia-meetings result <id>         # получить результат
```

В будущем — обёртка в нативное Mac-приложение (SwiftUI + menubar).

## Интеграция с AI-агентом

AI-агент использует REST API как tool:

```python
# Пример tool-описания для Claude Agent
{
    "name": "transcribe_meeting",
    "description": "Upload and transcribe a meeting audio file. Returns transcript, summary, action items.",
    "input_schema": {
        "type": "object",
        "properties": {
            "audio_url": {"type": "string", "description": "URL of the audio file"},
            "title": {"type": "string", "description": "Meeting title"},
            "language": {"type": "string", "default": "ru"}
        },
        "required": ["audio_url"]
    }
}
```

## Структура проекта

```
AIA-Meetings/
├── docs/
│   └── ARCHITECTURE.md
├── src/
│   ├── api/                    # FastAPI приложение
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app, middleware
│   │   ├── routes/
│   │   │   ├── meetings.py     # CRUD endpoints
│   │   │   └── webhooks.py     # webhook management
│   │   ├── models/
│   │   │   ├── meeting.py      # SQLAlchemy models
│   │   │   └── schemas.py      # Pydantic schemas
│   │   ├── services/
│   │   │   ├── transcription.py  # Yandex SpeechKit integration
│   │   │   ├── summarization.py  # Claude API integration
│   │   │   └── storage.py       # file storage
│   │   ├── tasks/
│   │   │   └── processing.py   # Celery tasks
│   │   ├── auth/
│   │   │   └── api_key.py      # API key validation
│   │   └── config.py           # settings
│   ├── bot/                    # Telegram bot
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── handlers/
│   │   │   ├── audio.py        # обработка аудио
│   │   │   └── commands.py     # /start, /meetings и пр.
│   │   └── keyboards.py
│   └── cli/                    # Mac CLI утилита
│       └── main.py
├── migrations/                 # Alembic миграции
├── tests/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## Конфигурация (.env)

```env
# API
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=...

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/aia_meetings

# Redis
REDIS_URL=redis://localhost:6379/0

# Yandex SpeechKit
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...

# Claude API
ANTHROPIC_API_KEY=...

# Telegram
TELEGRAM_BOT_TOKEN=...

# Storage
STORAGE_TYPE=local  # local | s3
STORAGE_PATH=/data/audio
```

## Деплой (рекомендация)

**Рекомендую: VPS + Docker Compose** для старта.

```yaml
# docker-compose.yml (упрощённо)
services:
  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, redis]

  worker:
    build: .
    command: celery -A src.api.tasks worker
    depends_on: [db, redis]

  bot:
    build: .
    command: python -m src.bot.main
    depends_on: [api]

  db:
    image: postgres:16

  redis:
    image: redis:7-alpine
```

**VPS**: Hetzner Cloud (CPX21 — 3 vCPU, 4GB RAM, ~€8/мес) — достаточно для MVP.

## Фазы реализации

### Фаза 1: MVP (core pipeline)
1. FastAPI-сервер с upload endpoint
2. Интеграция Yandex SpeechKit (async recognition)
3. Сохранение транскрипта в PostgreSQL
4. Claude API для саммари + action items
5. GET endpoint для получения результата
6. API Key авторизация
7. Docker Compose для локального запуска

### Фаза 2: Клиенты
8. Telegram-бот (aiogram 3)
9. CLI-утилита для Mac
10. Webhook-уведомления

### Фаза 3: Продакшен
11. Деплой на VPS
12. Мониторинг (Sentry, health checks)
13. Rate limiting, квоты

### Фаза 4: Расширение
14. Диаризация (разделение спикеров)
15. Real-time транскрипция (streaming)
16. Нативное Mac-приложение
17. Интеграция с календарём (auto-record)
