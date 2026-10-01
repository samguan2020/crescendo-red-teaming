"""
Strongly-typed application settings with fail-fast validation.

Precedence: OS env > backend/.env > defaults. Required secrets are validated
when settings are built at startup, so a misconfigured deploy fails loudly
instead of erroring on the first request.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Crescendo Backend"
    ENV: Literal["dev", "prod"] = "dev"

    # Attacker (Gemini)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Target (HuggingFace router)
    HUGGINGFACE_API_KEY: str = ""
    HUGGINGFACE_API_URL: str = "https://router.huggingface.co/v1"
    HUGGINGFACE_MODELS: dict[str, str] = {
        "llama3": "meta-llama/Llama-3.1-8B-Instruct",
        "qwen": "Qwen/Qwen2.5-7B-Instruct",
        "gemma": "google/gemma-3-27b-it",
        "deepseek": "deepseek-ai/DeepSeek-V3",
        "nemotron": "nvidia/NVIDIA-Nemotron-Nano-12B-v2",
        "kimi": "moonshotai/Kimi-K2-Instruct",
        "gpt-oss": "openai/gpt-oss-120b",
    }
    AVAILABLE_MODELS: list[str] = [
        "llama3", "qwen", "gemma", "deepseek", "nemotron", "kimi", "gpt-oss",
    ]

    # Storage
    DATABASE_URL: str = ""           # required (truth source)
    REDIS_URL: str = ""              # required unless USE_MEMORY_STORE
    USE_MEMORY_STORE: bool = False
    JOB_TTL: int = 86400             # Redis projection TTL (seconds)

    # Execution
    TASK_QUEUE: Literal["inprocess", "arq"] = "inprocess"
    DEFAULT_MAX_TURNS: int = 10

    # API / CORS
    API_KEY: str = ""
    ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    ALLOWED_ORIGIN_REGEX: str | None = None

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("ALLOWED_ORIGINS", "AVAILABLE_MODELS", mode="before")
    @classmethod
    def _parse_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _validate_required(self) -> "Settings":
        missing: list[str] = []
        if not self.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if not self.HUGGINGFACE_API_KEY:
            missing.append("HUGGINGFACE_API_KEY")
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.REDIS_URL and not self.USE_MEMORY_STORE:
            missing.append("REDIS_URL (or set USE_MEMORY_STORE=true for dev)")
        if missing:
            raise ValueError(
                "Missing required configuration: " + ", ".join(missing)
            )
        return self


def get_settings() -> Settings:
    """Build and validate settings. Call at startup (fail-fast)."""
    return Settings()
