"""Centralized application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "uploads"
SAMPLE_DIR = BASE_DIR / "samples"


class Settings(BaseSettings):
    app_name: str = "LegalLens AI"
    app_version: str = "1.0.0"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_lite_model: str = "gemini-3.6-flash-lite"
    generate_questions_model_depth: int = 1

    database_url: str = ""
    jwt_secret: str = "dev-only-change-me"
    frontend_url: str = "http://localhost:5173"

    enable_demo: bool = True
    force_demo: bool = False

    log_level: str = "INFO"
    rate_limit_per_minute: int = 30
    max_upload_size_mb: int = 20

    upload_dir: Path = UPLOAD_DIR
    demo_seed: Path = BASE_DIR / "app" / "db" / "demo_seed.json"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_url.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def real_ai_available(self) -> bool:
        """True when a Gemini API key is configured and not in forced demo mode."""
        return bool(self.gemini_api_key) and not self.force_demo


@lru_cache
def get_settings() -> Settings:
    if not os.path.exists(Settings.model_config.get("env_file")):
        _ = Settings.model_config
    return Settings()