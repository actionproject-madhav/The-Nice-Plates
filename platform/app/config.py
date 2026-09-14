"""Configuration.

One rule: nothing here has a production default. Anything secret defaults to
empty and the matching feature degrades loudly (see `/health/ready`) instead of
silently doing the wrong thing. Local dev works with an empty .env.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ── Runtime ──
    env: str = "development"
    log_level: str = "INFO"
    api_port: int = 8000

    # ── Frontend / CORS ──
    # Comma-separated. Vercel preview URLs are matched by regex below.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = r"https://.*\.vercel\.app"

    # ── Mongo ──
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "nice_plates"

    # ── Redis / queue ──
    redis_url: str = "redis://localhost:6379/0"
    analysis_queue: str = "queue:analysis"
    # Render's free tier has no background workers, so the API can host the
    # worker loop in-process. Flip to false the day the worker gets its own
    # service; nothing else changes.
    embedded_worker: bool = True

    # ── Auth ──
    google_client_id: str = ""
    jwt_secret: str = "dev-only-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24 * 7

    # ── Object storage (Cloudflare R2, S3-compatible) ──
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "nice-plates"
    r2_public_base_url: str = ""
    presign_ttl_seconds: int = 15 * 60
    # With no R2 credentials, uploads land in this directory and are served by
    # the API. Lets a teammate run the whole stack before any cloud signup.
    local_storage_dir: str = ".localstorage"

    # ── Coach (OpenAI) ──
    openai_api_key: str = ""
    # The cheap tier. Function calling is identical to the larger models, and
    # the coach's job — read three tool results, write 150 words — does not
    # need more. Roughly 1/15th the cost of gpt-4o per token.
    coach_model: str = "gpt-4o-mini"
    coach_max_tokens: int = 4096
    # Speech-to-text for spoken practice notes. Never used for note detection.
    whisper_model: str = "whisper-1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}

    @property
    def storage_configured(self) -> bool:
        return bool(self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key)

    @property
    def coach_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
