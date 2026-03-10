from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "change-me"

    # Database
    database_url: str = "postgresql+asyncpg://aia:aia_password@localhost:5432/aia_meetings"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Yandex SpeechKit
    yandex_api_key: str = ""
    yandex_folder_id: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # Storage
    storage_type: str = "local"
    storage_path: str = "/data/audio"

    # Celery
    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return self.redis_url

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
