"""Configuracion del dashboard web, separada de `video_translator.config.Settings`.

Lee `.env.web` (no `.env`, que es del pipeline CLI) via pydantic-settings.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.web", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://prosodia:prosodia@localhost:5432/prosodia")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Sin default seguro en produccion: se provee un valor claramente marcado
    # como inseguro para que el desarrollo local funcione sin crear un .env.web.
    jwt_secret_key: str = Field(default="CHANGE_ME_INSECURE_DEV_SECRET")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=720)

    storage_root: str = Field(default="./data/prosodia_web")

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )


def load_web_settings() -> WebSettings:
    return WebSettings()
