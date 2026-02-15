from sqlalchemy import create_engine, text, select, NullPool
import streamlit as st
import os

# os.environ.setdefault("RUST_LOG", "debug")
import libsql
from logging_config import setup_logging
import sqlite3 as sql
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
import threading
from contextlib import suppress
from time import perf_counter

logger = setup_logging(__name__)

# =============================================================================
# Doctrine Configuration Constants
# =============================================================================

# Default ship target stock level when not explicitly configured
# This value is used as the fallback when a fit or ship doesn't have a
# target defined in the ship_targets table
DEFAULT_SHIP_TARGET = 20

# =============================================================================
# Database Configuration
# =============================================================================

# Global lock to serialize sync operations within the process
_SYNC_LOCK = threading.Lock()


def get_settings() -> dict:
    from settings_service import SettingsService

    return SettingsService().settings_dict


class DatabaseConfig:
    settings = get_settings()
    # master config variable for the database to use
    wcdbmap = settings["env_db_aliases"][settings["env"]["env"]]

    # Build database paths dynamically from settings.toml [db_paths]
    _db_paths = {alias: path for alias, path in settings["db_paths"].items()}

    # Build Turso credentials dynamically — not all aliases need Turso
    # Use [db_turso_keys] overrides where secret name ≠ {alias}_turso
    _turso_key_overrides = settings.get("db_turso_keys", {})
    _db_turso_urls: dict[str, str] = {}
    _db_turso_auth_tokens: dict[str, str] = {}
    for _alias in _db_paths:
        _turso_key = f"{_alias}_turso"
        _secret_key = _turso_key_overrides.get(_alias, _turso_key)
        try:
            _db_turso_urls[_turso_key] = st.secrets[_secret_key].url
            _db_turso_auth_tokens[_turso_key] = st.secrets[_secret_key].token
        except (KeyError, AttributeError):
            pass  # Not all aliases need Turso (graceful degradation)

    # Shared handles per-alias to avoid multiple simultaneous connections to the same file
    _engines: dict[str, object] = {}
    _remote_engines: dict[str, object] = {}
    _libsql_connects: dict[str, object] = {}
    _libsql_sync_connects: dict[str, object] = {}
    _sqlite_local_connects: dict[str, object] = {}
    _ro_engines: dict[str, object] = {}

    @staticmethod
    def _resolve_active_alias() -> str:
        """Return the database alias for the currently active market.

        Reads ``active_market_key`` from Streamlit session state and maps
        it to the corresponding ``database_alias``.  Falls back to the
        static ``wcdbmap`` (from settings.toml) when session state is not
        available (e.g. during tests or CLI scripts).
        """
        try:
            from state.market_state import get_active_market
            return get_active_market().database_alias
        except Exception:
            return DatabaseConfig.wcdbmap

    def __init__(self, alias: str, dialect: str = "sqlite+libsql"):
        if alias in ("wcmkt", "wcmkt2", "wcmkt3"):
            if alias != "wcmkt":
                logger.warning(f"Alias {alias} is deprecated, resolving to active market")
            alias = self._resolve_active_alias()

        if alias not in self._db_paths:
            raise ValueError(
                f"Unknown database alias '{alias}'. "
                f"Available: {list(self._db_paths.keys())}"
            )
        self.alias = alias
        self.path = self._db_paths[alias]
        self.url = f"{dialect}:///{self.path}"
        turso_key = f"{self.alias}_turso"
        self.turso_url = self._db_turso_urls.get(turso_key)
        self.token = self._db_turso_auth_tokens.get(turso_key)
        self._engine = None
        self._remote_engine = None
        self._libsql_connect = None
        self._libsql_sync_connect = None
        self._sqlite_local_connect = None
        self._ro_engine = None

    @property
    def engine(self):
        eng = DatabaseConfig._engines.get(self.alias)
        if eng is None:
            eng = create_engine(self.url)
            DatabaseConfig._engines[self.alias] = eng
        return eng

    @property
    def remote_engine(self):
        eng = DatabaseConfig._remote_engines.get(self.alias)
        if eng is None:
            if not self.turso_url or not self.token:
                raise ValueError(
                    f"No Turso credentials for alias '{self.alias}'. "
                    "Add [{self.alias}_turso] to .streamlit/secrets.toml"
                )
            eng = create_engine(
                f"sqlite+{self.turso_url}?secure=true",
                connect_args={"auth_token": self.token},
            )
            DatabaseConfig._remote_engines[self.alias] = eng
        return eng

    @property
    def libsql_local_connect(self):
        conn = DatabaseConfig._libsql_connects.get(self.alias)
        if conn is None:
            conn = libsql.connect(self.path)
            DatabaseConfig._libsql_connects[self.alias] = conn
        return conn

    @property
    def libsql_sync_connect(self):
        conn = DatabaseConfig._libsql_sync_connects.get(self.alias)
        if conn is None:
            conn = libsql.connect(
                self.path, sync_url=self.turso_url, auth_token=self.token
            )
            DatabaseConfig._libsql_sync_connects[self.alias] = conn
        return conn

    @property
    def sqlite_local_connect(self):
        conn = DatabaseConfig._sqlite_local_connects.get(self.alias)
        if conn is None:
            conn = sql.connect(self.path)
            DatabaseConfig._sqlite_local_connects[self.alias] = conn
        return conn

    @property
    def ro_engine(self):
        """SQLAlchemy engine to the local file, read-only, no pooling."""
        eng = DatabaseConfig._ro_engines.get(self.alias)
        if eng is not None:
            return eng
        else:
            # URI form with read-only flags
            uri = f"sqlite+pysqlite:///file:{self.path}?mode=ro&uri=true"
            eng = create_engine(
                uri,
                poolclass=NullPool,  # no long-lived pooled handles
                connect_args={"check_same_thread": False},
            )
            DatabaseConfig._ro_engines[self.alias] = eng
        return eng

    def _dispose_local_connections(self):
        """Dispose/close all local connections/engines to safely allow file operations.
        This helps prevent corruption during sync by ensuring no open handles.
        """
        # Dispose SQLAlchemy engine (local file) shared across instances
        eng = DatabaseConfig._engines.pop(self.alias, None)
        if eng is not None:
            with suppress(Exception):
                eng.dispose()

        # Close libsql direct connection if any
        conn = DatabaseConfig._libsql_connects.pop(self.alias, None)
        if conn is not None:
            with suppress(Exception):
                conn.close()

        # Close libsql sync connection if any (avoid reusing for sync)
        sconn = DatabaseConfig._libsql_sync_connects.pop(self.alias, None)
        if sconn is not None:
            with suppress(Exception):
                sconn.close()

        # Close raw sqlite3 connection if any
        sqlite_conn = DatabaseConfig._sqlite_local_connects.pop(self.alias, None)
        if sqlite_conn is not None:
            with suppress(Exception):
                sqlite_conn.close()

        # Close read-only engine if any
        ro_engine = DatabaseConfig._ro_engines.pop(self.alias, None)
        if ro_engine is not None:
            with suppress(Exception):
                ro_engine.dispose()

    def integrity_check(self) -> bool:
        """Run PRAGMA integrity_check on the local database.

        Returns True if the result is 'ok', False otherwise or on error.
        """
        try:
            # Use a short-lived connection
            with self.engine.connect() as conn:
                result = conn.execute(text("PRAGMA integrity_check")).fetchone()
                logger.debug(f"integrity_check() result: {result}")
            status = str(result[0]).lower() if result and result[0] is not None else ""
            ok = status == "ok"
            return ok
        except Exception as e:
            logger.error(f"Integrity check error ({self.alias}): {e}")
            return False

    def _sync_once(self) -> bool:
        """Execute a single sync attempt against the remote Turso replica.

        Creates a libsql embedded-replica connection, syncs, verifies the
        data is current via the *same* connection, then closes.

        Returns True if sync succeeded and the local data matches remote.
        """
        sync_start = perf_counter()
        file_existed_before = os.path.exists(self.path)
        conn = None
        try:
            conn = libsql.connect(
                self.path, sync_url=self.turso_url, auth_token=self.token
            )
            conn.sync()
            sync_time = round((perf_counter() - sync_start) * 1000, 2)
            logger.info(
                f"sync() completed for {self.alias} in {sync_time} ms at "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Verify the sync actually pulled data by reading from the
            # SAME connection (before close).  If the local file had stale
            # embedded-replica metadata from a different Turso database,
            # the sync silently does nothing and this check catches it.
            try:
                row = conn.execute(
                    "SELECT MAX(last_update) FROM marketstats"
                ).fetchone()
                local_ts = row[0] if row else None
                logger.info(f"Post-sync local MAX(last_update) via sync conn: {local_ts}")
            except Exception:
                local_ts = None

            return True
        except Exception as e:
            logger.error(f"Database sync failed for {self.alias}: {e}")
            if not file_existed_before:
                self._cleanup_empty_db_file()
            raise
        finally:
            if conn is not None:
                with suppress(Exception):
                    conn.close()
                    logger.info("Sync connection closed")

    def sync(self) -> bool:
        """Synchronize the local database with the remote Turso replica safely.

        Uses _SYNC_LOCK to serialize sync operations and disposes local
        connections to prevent corruption.

        If the first sync attempt leaves stale data (e.g. because the local
        file had embedded-replica metadata from a different Turso database),
        the local file is deleted and a fresh sync is attempted.

        Returns:
            True if sync and integrity check succeeded, False otherwise.
            Callers are responsible for cache invalidation and UI feedback.

        Raises:
            ValueError: If Turso credentials are missing for this alias.
        """
        # Fail fast before libsql.connect() can create an empty db file
        if not self.turso_url or not self.token:
            raise ValueError(
                f"Missing Turso credentials for alias '{self.alias}'. "
                f"Add [{self.alias}_turso] section to .streamlit/secrets.toml"
            )

        logger.info("-" * 40)
        logger.info(
            f"sync() starting for {self.alias} "
            f"(url={self.turso_url}) at "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        with _SYNC_LOCK:
            self._dispose_local_connections()
            logger.debug("Disposed local connections, starting sync...")

            self._sync_once()

            # Verify local data matches remote.  If it doesn't, the local
            # file likely has replica metadata from a different Turso DB
            # (e.g. the old static wcdbmap).  Delete and retry from scratch.
            if not self._local_matches_remote():
                logger.warning(
                    f"Post-sync data mismatch for {self.alias} — "
                    "local file may have stale replica metadata. "
                    "Deleting local file and retrying fresh sync."
                )
                self._dispose_local_connections()
                self._cleanup_empty_db_file()
                self._sync_once()

                if not self._local_matches_remote():
                    logger.error(
                        f"Fresh sync for {self.alias} still has data mismatch"
                    )

            update_time = datetime.now(timezone.utc)
            logger.info(f"Database synced at {update_time} UTC")
            logger.info("-" * 40)

            # Post-sync integrity validation
            ok = self.integrity_check()
            if not ok:
                logger.error("Post-sync integrity check failed.")

            return ok

    def _local_matches_remote(self) -> bool:
        """Check if local MAX(last_update) matches remote after sync.

        Uses a plain sqlite3 read-only connection for the local read to
        avoid any libsql driver caching or replica-state issues.
        """
        try:
            # Read remote via Turso
            with self.remote_engine.connect() as conn:
                row = conn.execute(
                    text("SELECT MAX(last_update) FROM marketstats")
                ).fetchone()
                remote_ts = row[0] if row else None

            # Read local via plain sqlite3 (bypasses libsql driver entirely)
            local_conn = sql.connect(f"file:{self.path}?mode=ro", uri=True)
            try:
                row = local_conn.execute(
                    "SELECT MAX(last_update) FROM marketstats"
                ).fetchone()
                local_ts = row[0] if row else None
            finally:
                local_conn.close()

            logger.info(
                f"_local_matches_remote({self.alias}): "
                f"remote={remote_ts}, local={local_ts}"
            )
            return remote_ts is not None and remote_ts == local_ts
        except Exception as e:
            logger.warning(f"_local_matches_remote check failed: {e}")
            return False

    def _cleanup_empty_db_file(self):
        """Remove empty db file and libsql/WAL artifacts left by a failed sync."""
        for suffix in ("", "-shm", "-wal", "-info"):
            file_path = self.path + suffix
            if os.path.exists(file_path):
                with suppress(OSError):
                    os.remove(file_path)
                    logger.info(f"Removed {file_path} created during failed sync")

    def validate_sync(self) -> bool:
        alias = self.alias
        with self.remote_engine.connect() as conn:
            result = conn.execute(
                text("SELECT MAX(last_update) FROM marketstats")
            ).fetchone()
            remote_last_update = datetime.strptime(
                result[0], "%Y-%m-%d %H:%M:%S.%f"
            ).replace(tzinfo=timezone.utc)
            conn.close()
        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT MAX(last_update) FROM marketstats")
            ).fetchone()
            local_last_update = datetime.strptime(
                result[0], "%Y-%m-%d %H:%M:%S.%f"
            ).replace(tzinfo=timezone.utc)
            conn.close()
        logger.info("-" * 40)
        logger.info(f"alias: {alias} validate_sync()")
        timestamp = datetime.now(tz=timezone.utc)
        local_timestamp = datetime.now(tz=ZoneInfo("US/Eastern"))
        logger.info(
            f"time: {local_timestamp.strftime('%Y-%m-%d %H:%M:%S')} (local); {
                timestamp.strftime('%Y-%m-%d %H:%M:%S')
            } (utc)"
        )
        logger.info(
            f"REMOTE LAST UPDATE: {
                remote_last_update.strftime('%Y-%m-%d %H:%M')
            } | Minutes ago: {
                round((timestamp - remote_last_update).total_seconds() / 60, 0)
            }"
        )
        logger.info(
            f"LOCAL LAST UPDATE: {
                local_last_update.strftime('%Y-%m-%d %H:%M')
            } | Minutes ago: {
                round((timestamp - local_last_update).total_seconds() / 60, 0)
            }"
        )
        logger.info("-" * 40)
        validation_test = remote_last_update == local_last_update
        logger.info(f"validation_test: {validation_test}")
        return validation_test

    def get_table_list(self, local_only: bool = True) -> list[tuple]:
        if local_only:
            engine = self.engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [
                    table.name for table in tables if "sqlite" not in table.name
                ]
                conn.close()
                return table_list
        else:
            engine = self.remote_engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [
                    table.name for table in tables if "sqlite" not in table.name
                ]
                conn.close()
                return table_list

    def get_table_columns(
        self, table_name: str, local_only: bool = True, full_info: bool = False
    ) -> list[dict]:
        """
        Get column information for a specific table.

        Args:
            table_name: Name of the table to inspect
            local_only: If True, use local database; if False, use remote database

        Returns:
            List of dictionaries containing column information
        """
        if local_only:
            engine = self.engine
        else:
            engine = self.remote_engine

        with engine.connect() as conn:
            # Use string formatting for PRAGMA since it doesn't support parameterized queries well
            stmt = text(f"PRAGMA table_info({table_name})")
            result = conn.execute(stmt)
            columns = result.fetchall()
            if full_info:
                column_info = []
                for col in columns:
                    column_info.append(
                        {
                            "cid": col.cid,
                            "name": col.name,
                            "type": col.type,
                            "notnull": col.notnull,
                            "dflt_value": col.dflt_value,
                            "pk": col.pk,
                        }
                    )
            else:
                column_info = [col.name for col in columns]
            conn.close()
            return column_info

    def get_most_recent_update(self, table_name: str, remote: bool = False) -> datetime:
        """
        Get the most recent update time for a specific table
        Args:
            table_name: str - The name of the table to get the most recent update time for
            remote: bool - If True, get the most recent update time from the remote database, if False, get the most recent update time from the local database

        Returns:
            The most recent update time for the table
        """
        from models import UpdateLog

        engine = self.remote_engine if remote else self.engine
        session = Session(bind=engine)
        with session.begin():
            updates = (
                select(UpdateLog.timestamp)
                .where(UpdateLog.table_name == table_name)
                .order_by(UpdateLog.timestamp.desc())
            )
            result = session.execute(updates).fetchone()
            update_time = result[0] if result is not None else None
            update_time = (
                update_time.replace(tzinfo=timezone.utc)
                if update_time is not None
                else None
            )
        session.close()
        engine.dispose()
        return update_time

    def get_time_since_update(
        self, table_name: str = "marketstats", remote: bool = False
    ):
        status = self.get_most_recent_update(table_name, remote=remote)
        now = datetime.now(tz=timezone.utc)
        time_since = now - status
        logger.info(f"update_time: {status.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"time_since: {round(time_since.total_seconds() / 60, 1)} minutes")
        return time_since if time_since is not None else None


if __name__ == "__main__":
    pass
