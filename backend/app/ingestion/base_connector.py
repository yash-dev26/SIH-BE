"""BaseSourceConnector: the pluggable-adapter contract every ingestion source
implements (Section 2.1's agent instruction).

Every connector:
  1. fetch()      -> raw pd.DataFrame from the upstream source
  2. validate()   -> Pandera-checked DataFrame (raises DataValidationError)
  3. normalize()  -> list of ORM row objects ready to persist
  4. run()        -> orchestrates 1-3, writes rows, and on SourceUnavailableError
                     falls back to fallback() (backed by SyntheticDataGenerator),
                     logging the degradation to data_quality_log rather than
                     failing silently or crashing the Celery Beat cycle.

Connectors never call session.commit() from fetch/validate/normalize — only
run()/to_raw_lake() touch persistence, keeping the pure-transform steps unit
testable without a database.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.ingestion.exceptions import DataValidationError, SourceUnavailableError
from app.ingestion.models import DataQualityLog

logger = logging.getLogger(__name__)


@dataclass
class ConnectorRunResult:
    connector_name: str
    provenance: str  # 'live' | 'proxy' | 'synthetic'
    rows_written: int
    started_at: datetime
    finished_at: datetime
    fallback_used: bool = False
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


class BaseSourceConnector(abc.ABC):
    """Subclass and implement fetch/validate/normalize/to_orm_rows.

    Class attributes each subclass should set:
        name:                short slug used in logs & data_quality_log rows
        default_provenance:  the provenance tag used when fetch() succeeds
                              against the *real* source ('live' or 'proxy')
    """

    name: str = "base_connector"
    default_provenance: str = "proxy"

    def __init__(self, session_factory=None) -> None:
        # Imported lazily so this module has no hard dependency on the
        # concrete session factory location at import time.
        if session_factory is None:
            from app.db.session import SessionLocal

            session_factory = SessionLocal
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Contract every connector must implement
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def fetch(self, **kwargs) -> pd.DataFrame:
        """Hit the real upstream source. Raise SourceUnavailableError if it
        cannot be reached, is paywalled, or its response can't be parsed."""

    @abc.abstractmethod
    def validate(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Run the Pandera schema for this series (see validation/expectations.py)
        and return the validated (possibly filtered) DataFrame. Raise
        DataValidationError on unrecoverable schema violations."""

    @abc.abstractmethod
    def normalize(self, validated: pd.DataFrame) -> list[Any]:
        """Map validated rows to ORM model instances ready for bulk insert."""

    def fallback(self, **kwargs) -> pd.DataFrame:
        """Produce a synthetic DataFrame shaped like fetch()'s output.
        Default raises — connectors backed by SyntheticDataGenerator should
        override this."""
        raise NotImplementedError(f"{self.name} has no synthetic fallback implemented")

    # ------------------------------------------------------------------
    # Shared orchestration — subclasses generally do not override this
    # ------------------------------------------------------------------
    def to_raw_lake(self, session: Session, rows: list[Any]) -> int:
        if not rows:
            return 0
        session.add_all(rows)
        session.flush()
        return len(rows)

    def run(self, **kwargs) -> ConnectorRunResult:
        started = datetime.now(timezone.utc)
        session = self._session_factory()
        fallback_used = False
        provenance = self.default_provenance
        error_msg: str | None = None
        written = 0
        try:
            try:
                raw = self.fetch(**kwargs)
                validated = self.validate(raw)
                rows = self.normalize(validated)
                written = self.to_raw_lake(session, rows)
            except SourceUnavailableError as exc:
                logger.warning(
                    "connector_source_unavailable connector=%s reason=%s", self.name, exc.reason
                )
                fallback_used = True
                error_msg = str(exc)
                raw = self.fallback(**kwargs)
                validated = self.validate(raw)
                rows = self.normalize(validated)
                written = self.to_raw_lake(session, rows)
                provenance = "synthetic"
                self._log_quality_event(
                    session,
                    status="fallback_used",
                    resolved_provenance=provenance,
                    reason=exc.reason,
                    rows_written=written,
                    context=kwargs,
                )
            except DataValidationError as exc:
                logger.error("connector_validation_failed connector=%s errors=%s", self.name, exc.errors)
                error_msg = str(exc)
                self._log_quality_event(
                    session,
                    status="validation_error",
                    resolved_provenance=None,
                    reason=str(exc),
                    rows_written=0,
                    context=kwargs,
                )
                session.commit()
                raise
            session.commit()
        except DataValidationError:
            # Already logged above; re-raise so the Celery task surfaces the
            # failure in its own status, rather than reporting false success.
            raise
        except Exception as exc:  # last-resort catch: never crash the Beat cycle silently
            session.rollback()
            logger.exception("connector_run_failed connector=%s", self.name)
            error_msg = str(exc)
            fresh = self._session_factory()
            try:
                self._log_quality_event(
                    fresh,
                    status="failed",
                    resolved_provenance=None,
                    reason=str(exc),
                    rows_written=0,
                    context=kwargs,
                )
                fresh.commit()
            finally:
                fresh.close()
        finally:
            session.close()

        finished = datetime.now(timezone.utc)
        return ConnectorRunResult(
            connector_name=self.name,
            provenance=provenance,
            rows_written=written,
            started_at=started,
            finished_at=finished,
            fallback_used=fallback_used,
            error=error_msg,
        )

    def _log_quality_event(
        self,
        session: Session,
        *,
        status: str,
        resolved_provenance: str | None,
        reason: str,
        rows_written: int,
        context: dict[str, Any],
    ) -> None:
        session.add(
            DataQualityLog(
                connector_name=self.name,
                status=status,
                resolved_provenance=resolved_provenance,
                reason=reason[:500],
                rows_written=rows_written,
                context={k: str(v) for k, v in context.items()},
            )
        )
