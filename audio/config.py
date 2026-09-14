"""Worker configuration. Reads the same env vars as the API."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    env: str = "development"
    log_level: str = "INFO"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "nice_plates"

    redis_url: str = "redis://localhost:6379/0"
    analysis_queue: str = "queue:analysis"
    # How long BLPOP waits before falling through to a Mongo sweep.
    block_seconds: int = 5
    # Backstop for jobs whose Redis message was lost.
    sweep_every_seconds: int = 30
    max_attempts: int = 3

    # Voice notes only. Note detection never calls OpenAI.
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "nice-plates"
    local_storage_dir: str = ".localstorage"

    @property
    def storage_configured(self) -> bool:
        return bool(self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key)


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()


settings = get_settings()
