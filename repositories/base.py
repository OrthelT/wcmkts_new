"""
Base Repository

Provides the foundation for all repository classes. Implements the common
read_df() pattern with malformed-DB recovery and backup-restore fallback.
(Originally extracted from the now-deleted db_handler.py in Phase 10.)

Design Principles:
1. Dependency Injection - Receives DatabaseConfig, doesn't create it
2. Malformed DB Recovery - Syncs and retries on corruption, falls back to
   restoring the last known-good backup on sync failure
3. Consistent interface - All repositories inherit this pattern
"""

from typing import Any, Mapping, Optional
import logging
import pandas as pd

from config import DatabaseConfig
from logging_config import setup_logging

logger = setup_logging(__name__)

# Error substrings that indicate a damaged/incomplete local replica (vs. a
# caller bug like bad SQL). Verified against pyturso's actual messages —
# see tests/test_base_repository.py.
MALFORMED_MARKERS: tuple[str, ...] = (
    "malform",
    "file is not a database",
    "no such table",
    "disk i/o error",
    "invalid page size",
)


def _is_malformed_error(msg: str) -> bool:
    return any(marker in msg for marker in MALFORMED_MARKERS)


class BaseRepository:
    """
    Base class for all repository implementations.

    Provides read_df() with automatic malformed-DB recovery:
    1. Try local read
    2. On malformed/corrupt error -> sync + retry local
    3. If sync fails -> restore_from_backup() + retry local
    4. If that fails -> raise

    Attributes:
        db: DatabaseConfig instance for database access
    """

    def __init__(self, db: DatabaseConfig, logger_instance: Optional[logging.Logger] = None):
        """
        Initialize repository with database configuration.

        Args:
            db: DatabaseConfig instance
            logger_instance: Optional logger (defaults to module logger)
        """
        self.db = db
        self._logger = logger_instance or logger

    def read_df(
        self,
        query: Any,
        params: Mapping[str, Any] | None = None,
        *,
        recover: bool = True,
    ) -> pd.DataFrame:
        """Execute a read-only SQL query and return a DataFrame.

        Recovery ladder on malformed/corrupt local databases:
          1. local read via db.engine
          2. on malformed-class error -> db.sync() + retry local
             (sync's state machine nukes + re-bootstraps when needed)
          3. if that fails -> db.restore_from_backup() + retry local
          4. raise -- caller surfaces an explicit error/empty state

        Args:
            query: SQL string or SQLAlchemy TextClause
            params: optional query parameters
            recover: set False to skip the recovery ladder (no mid-request
                multi-second sync); the original error raises immediately.
        """

        def _run_local() -> pd.DataFrame:
            with self.db.engine.connect() as conn:
                return pd.read_sql_query(query, conn, params=params)

        try:
            return _run_local()
        except Exception as e:
            if not (recover and _is_malformed_error(str(e).lower())):
                raise
            self._logger.error(
                f"Local DB error ('{e}'); attempting sync + retry, "
                "then backup restore..."
            )
            try:
                self.db.sync()
                return _run_local()
            except Exception:
                self._logger.error(
                    "Sync recovery failed; attempting backup restore."
                )
            if self.db.restore_from_backup():
                return _run_local()
            raise
