from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FreightIQ Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"

    # Database
    DATABASE_URL: str = "sqlite:///./freightiq.db"  # Defaults to local SQLite for standalone execution

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False  # Set to True when Redis/Celery is running; False runs tasks synchronously/in-memory

    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    ARTIFACTS_DIR: Path = BASE_DIR / "artifacts" / "models"

    # Model Parameters
    DEFAULT_RETRAIN_MARGIN_PCT: float = 2.0  # Require 2% improvement to promote challenger model
    USE_SYNTHETIC_DATA: bool = True

    # Optimization / Recommendation Engine (Phase 4)
    DEFAULT_SPOT_CAP_RATIO: float = 0.4  # Section 3.2 constraint 9: max share of cargo volume on SPOT contracts
    FULL_OPTIMIZATION_PARCEL_THRESHOLD: int = 3  # >N parcels (or explicit full_optimization=true) routes to the async CP-SAT solver
    MILP_SOLVER_TIME_LIMIT_SECONDS: float = 10.0
    IDLE_MITIGATION_TOP_N: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def init_directories(self) -> None:
        """Ensure necessary directories exist."""
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.init_directories()



