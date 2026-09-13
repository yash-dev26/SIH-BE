"""
Central application configuration.

Non-negotiable per the implementation plan (Section 0): no hardcoded business
constants (draft limits, port lists, vessel class definitions, etc.) — those
live in DB seed data (backend/seed_data/*.yaml) or here as *infrastructure*
config only. This module holds infra/runtime settings, never domain constants.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg://freightiq:freightiq@localhost:5432/freightiq",
        alias="DATABASE_URL",
    )

    # --- Celery / Redis ---
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1", alias="CELERY_RESULT_BACKEND"
    )

    # --- API ---
    api_port: int = Field(default=8000, alias="API_PORT")

    # --- Data strategy ---
    use_synthetic_data: bool = Field(default=True, alias="USE_SYNTHETIC_DATA")

    # --- Third-party credentials (Phase 2+; all optional, connectors must
    #     stub/fallback gracefully when unset — see Section 5.3) ---
    trading_economics_api_key: str | None = Field(default=None, alias="TRADING_ECONOMICS_API_KEY")
    eia_api_key: str | None = Field(default=None, alias="EIA_API_KEY")
    aishub_api_key: str | None = Field(default=None, alias="AISHUB_API_KEY")
    marinetraffic_api_key: str | None = Field(default=None, alias="MARINETRAFFIC_API_KEY")
    incois_api_key: str | None = Field(default=None, alias="INCOIS_API_KEY")

    # --- Model registry (MVP: filesystem artifact store) ---
    model_registry_artifact_dir: Path = Field(
        default=BACKEND_ROOT / "model_artifacts", alias="MODEL_REGISTRY_ARTIFACT_DIR"
    )

    # --- Auth (Phase 5) ---
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # --- Paths ---
    seed_data_dir: Path = Field(default=BACKEND_ROOT / "seed_data")


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import and call this, don't instantiate Settings() directly."""
    return Settings()
