"""
Base Repository

Provides the foundation for all repository classes. Implements the common
read_df() pattern with malformed-DB recovery.
(Originally extracted from the now-deleted db_handler.py in Phase 10.)

Design Principles:
1. Dependency Injection - Receives DatabaseConfig, doesn't create it
2. Malformed DB Recovery - Rebuilds the replica from Turso and retries
3. Consistent interface - All repositories inherit this pattern
"""

from contextlib import contextmanager
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
    # pyturso on a truncated replica: "I/O error: short read on page 1:
    # expected 512 bytes, got 100". Matching the whole phrase rather than
    # broadening "disk i/o error" to "i/o error", which would swallow
    # transient faults that a rebuild cannot fix.
    "short read",
)


def _is_malformed_error(msg: str) -> bool:
    return any(marker in msg for marker in MALFORMED_MARKERS)


@contextmanager
def _rebuild_status(alias: str):
    """Show a spinner while a recovery sync rebuilds ``alias``'s replica.

    A rebuild pull re-downloads the whole database (~20 s on the primary
    hub); without this the page just stalls with no explanation. Streamlit
    is imported lazily and used only inside an active script run, so
    repositories stay usable from tests, the CLI, and worker threads.
    """
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        in_script_run = get_script_run_ctx() is not None
    except Exception:  # Streamlit absent, or its internals moved
        in_script_run = False
    if not in_script_run:
        yield
        return
    with st.spinner(f"Rebuilding local database ({alias})…"):
        yield


class BaseRepository:
    """
    Base class for all repository implementations.

    Provides read_df() with automatic malformed-DB recovery:
    1. Try local read
    2. On malformed/corrupt error -> sync + retry local
    3. If that fails -> raise

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
          3. raise -- caller surfaces an explicit error/empty state

        Turso holds the durable copy, so a rebuild is the only recovery:
        there is no local backup to fall back to.

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
                f"Local DB error ('{e}'); rebuilding {self.db.alias} from "
                "Turso and retrying..."
            )
            with _rebuild_status(self.db.alias):
                self.db.sync()
                return _run_local()
