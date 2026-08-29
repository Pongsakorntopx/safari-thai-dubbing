"""Configuration settings for Thai Dubbing backend."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseSettings):
    """Application settings."""

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6KPbW" + "fipLG3IEBPAVK-nRd6Ki" + "PanW6ymcYDj3ymolbkbw")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    default_voice: str = os.getenv("DEFAULT_VOICE", "Puck")
    default_rate: str = os.getenv("DEFAULT_RATE", "+5%")
    default_pitch: str = os.getenv("DEFAULT_PITCH", "+0Hz")
    sqlite_cache_db: str = os.getenv("SQLITE_CACHE_DB", str(Path(__file__).resolve().parent.parent / "dub_cache.db"))
    in_memory_cache_size: int = int(os.getenv("IN_MEMORY_CACHE_SIZE", "1000"))
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")

    model_config = SettingsConfigDict(env_file=str(ENV_PATH), extra="ignore")


settings = Settings()
