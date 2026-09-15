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

    # Section 5.2: charter_contracts.laytime_allowed_days / demurrage_rate_usd_per_day are nullable
    # and default to these configurable market-standard assumptions when a contract hasn't
    # negotiated its own terms yet.
    DEFAULT_LAYTIME_ALLOWED_DAYS: float = 4.0
    DEFAULT_DEMURRAGE_RATE_USD_PER_DAY: float = 12000.0

    # --- Phase 5: API Layer & Auth ---
    # Minimal single-role (logistics_manager) OAuth2/JWT auth for MVP. `User.role` is already
    # a free-text column so multi-role RBAC (analyst/manager/admin) is additive later, not a
    # rewrite. AUTH_ENABLED defaults to False so read endpoints and the existing Phase 1-4
    # test/smoke suites keep working unauthenticated; flip to True once a frontend client
    # ships a login flow, and set a real SECRET_KEY via env in any non-local deployment.
    AUTH_ENABLED: bool = False
    SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    DEFAULT_ADMIN_USERNAME: str = "logistics_manager"
    DEFAULT_ADMIN_PASSWORD: str = "changeme123"

    # Rate limiting (Section 4, Phase 5 task 4): simple fixed-window limit per client IP.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "120/minute"

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





