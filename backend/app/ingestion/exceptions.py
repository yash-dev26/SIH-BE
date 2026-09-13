"""Exceptions used across ingestion connectors.

Per the implementation plan (Section 2.1 / Phase 2 task 2):
    "Any connector hitting a paywalled/inaccessible source must raise a clear
    SourceUnavailableError that is caught by an orchestrator which falls back
    to SyntheticDataGenerator for that specific series without silently
    failing — log + flag in a data_quality_log table."
"""

from __future__ import annotations


class SourceUnavailableError(Exception):
    """Raised by a connector's fetch() when the upstream source cannot be
    reached or parsed (paywall, network failure, schema change, rate limit).

    This is NOT used for "the source returned zero new rows" (that's a
    normal, quiet outcome) — only for genuine inability to retrieve data.
    """

    def __init__(self, connector_name: str, reason: str, *, series: str | None = None) -> None:
        self.connector_name = connector_name
        self.reason = reason
        self.series = series
        super().__init__(
            f"[{connector_name}] source unavailable"
            f"{f' ({series})' if series else ''}: {reason}"
        )


class DataValidationError(Exception):
    """Raised when fetched data fails its Pandera schema checks and cannot
    be safely written to the raw lake / persistence layer."""

    def __init__(self, connector_name: str, errors: str) -> None:
        self.connector_name = connector_name
        self.errors = errors
        super().__init__(f"[{connector_name}] validation failed: {errors}")
