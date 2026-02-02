"""
Base Repository

Provides the foundation for all repository classes. Extracts the common
read_df() pattern from db_handler.py with malformed-DB recovery and
remote fallback.

Design Principles:
1. Dependency Injection - Receives DatabaseConfig, doesn't create it
2. Malformed DB Recovery - Syncs and retries on corruption, falls back to remote
3. Consistent interface - All repositories inherit this pattern
"""

from typing import Any, Mapping, Optional
import logging
import pandas as pd

from config import DatabaseConfig
from logging_config import setup_logging

logger = setup_logging(__name__)


class BaseRepository:
    """
    Base class for all repository implementations.

    Provides read_df() with automatic malformed-DB recovery:
    1. Try local read
    2. On malformed/corrupt error -> sync + retry local
    3. If retry fails -> fall back to remote read

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
        local: bool = True,
        fallback_remote_on_malformed: bool = True,
    ) -> pd.DataFrame:
        """Execute a read-only SQL query and return a DataFrame.

        Uses db.engine for local reads with automatic recovery on
        malformed/corrupt databases.

        Data flow:
          1. local read via db.engine
          2. on malformed error -> db.sync() + retry local
          3. if retry fails -> remote read via db.remote_engine

        Args:
            query: SQL query string or SQLAlchemy TextClause
            params: Optional query parameters
            local: If False, read directly from remote
            fallback_remote_on_malformed: If True, fall back to remote on DB errors

        Returns:
            DataFrame with query results
        """

        def _run_local() -> pd.DataFrame:
            with self.db.engine.connect() as conn:
                return pd.read_sql_query(query, conn, params=params)

        def _run_remote() -> pd.DataFrame:
            with self.db.remote_engine.connect() as conn:
                return pd.read_sql_query(query, conn, params=params)

        if not local:
            return _run_remote()

        try:
            return _run_local()

        except Exception as e:
            msg = str(e).lower()
            if fallback_remote_on_malformed and (
                "malform" in msg
                or "database disk image is malformed" in msg
                or "no such table" in msg
            ):
                self._logger.error(
                    f"Local DB error ('{msg}'); syncing and retrying, "
                    f"with remote fallback..."
                )
                try:
                    self.db.sync()
                    return _run_local()
                except Exception:
                    self._logger.error(
                        "Failed to sync local DB; falling back to remote read."
                    )
                    return _run_remote()
            raise
