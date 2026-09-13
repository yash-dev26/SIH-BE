"""SQLAlchemy engine/session wiring. Used by both the API (via FastAPI dependency)
and standalone scripts (seed scripts, Celery tasks)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped session, always closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
