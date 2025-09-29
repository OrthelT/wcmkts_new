from sqlalchemy import create_engine, text, select, event
from sqlalchemy.pool import NullPool
import streamlit as st
import libsql
from logging_config import setup_logging
import sqlite3 as sql
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models import UpdateLog
import threading
from contextlib import suppress, contextmanager

import os
import contextlib
try:
    import fcntl  # Unix
    _HAVE_FCNTL = True
except Exception:
    fcntl = None
    _HAVE_FCNTL = False

@contextlib.contextmanager
def _sync_filelock(lock_path: str):
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    acquired = False
    try:
        if _HAVE_FCNTL:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                acquired = False
        else:
            import msvcrt  # type: ignore
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                acquired = False
        yield acquired
    finally:
        try:
            if acquired:
                if _HAVE_FCNTL:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                else:
                    import msvcrt  # type: ignore
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)

logger = setup_logging(__name__)

# Global lock to serialize sync operations within the process
_SYNC_LOCK = threading.Lock()

class DatabaseConfig:

    wcdbmap = "wcmkt2" #master config variable for the database to use

    _db_paths = {
        "wcmkt2": "wcmkt2.db", #production database
        "sde": "sde_lite.db",
        "build_cost": "buildcost.db",
        "wcmkt3": "wcmkt3.db" #testing db

    }

    _db_turso_urls = {
        "wcmkt2_turso": st.secrets.wcmkt2_turso.url,
        "sde_turso": st.secrets.sde_lite_turso.url,
        "build_cost_turso": st.secrets.buildcost_turso.url,
        "wcmkt3_turso": st.secrets.wcmkt3_turso.url,
    }

    _db_turso_auth_tokens = {
        "wcmkt2_turso": st.secrets.wcmkt2_turso.token,
        "sde_turso": st.secrets.sde_lite_turso.token,
        "build_cost_turso": st.secrets.buildcost_turso.token,
        "wcmkt3_turso": st.secrets.wcmkt3_turso.token,
    }

    # Shared handles per-alias to avoid multiple simultaneous connections to the same file
    _engines: dict[str, object] = {}
    _remote_engines: dict[str, object] = {}
    _libsql_connects: dict[str, object] = {}
    _libsql_sync_connects: dict[str, object] = {}
    _sqlite_local_connects: dict[str, object] = {}
    _local_locks: dict[str, threading.RLock] = {}
    _ro_engines: dict[str, object] = {}

    def __init__(self, alias: str, dialect: str = "sqlite+libsql"):
        if alias == "wcmkt":
            alias = self.wcdbmap
        elif alias == "wcmkt2" or alias == "wcmkt3":
            logger.warning(f"Alias {alias} is deprecated, using {self.wcdbmap} instead")
            alias = self.wcdbmap

        if alias not in self._db_paths:
            raise ValueError(f"Unknown database alias '{alias}'. "
                             f"Available: {list(self._db_paths.keys())}")
        self.alias = alias
        self.path = self._db_paths[alias]
        self.url = f"{dialect}:///{self.path}"
        self.turso_url = self._db_turso_urls[f"{self.alias}_turso"]
        self.token = self._db_turso_auth_tokens[f"{self.alias}_turso"]
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
            turso_url = self._db_turso_urls[f"{self.alias}_turso"]
            auth_token = self._db_turso_auth_tokens[f"{self.alias}_turso"]
            eng = create_engine(
                f"sqlite+{turso_url}?secure=true",
                connect_args={"auth_token": auth_token},
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
            conn = libsql.connect(self.path, sync_url=self.turso_url, auth_token=self.token)
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
                poolclass=NullPool,                  # no long-lived pooled handles
                connect_args={"check_same_thread": False},
            )
            DatabaseConfig._ro_engines[self.alias] = eng
        return eng

        # @event.listens_for(eng, "connect")
        # def _set_pragmas(dbapi_con, _):
        #     logger.info("Setting PRAGMAS for read-only engine")
        #     cur = dbapi_con.cursor()
        #     cur.execute("PRAGMA read_uncommitted=0;")
        #     cur.execute("PRAGMA mmap_size=0;")   # avoid stale mappings
        #     cur.execute("PRAGMA busy_timeout=250;")
        #     cur.close()

        self._ro_engine = eng
        return eng

    @contextmanager
    def local_access(self):
        """Guard local DB access to avoid overlapping with sync."""
        pass
        # lock = self._get_local_lock()
        # lock.acquire()
        # try:
        #     logger.debug(f"local_access() lock acquired for {self.alias}")
        #     yield
        # finally:
        #     lock.release()
        #     logger.debug(f"local_access() lock released for {self.alias}")

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

    def _get_local_lock(self) -> threading.RLock:
        lock = DatabaseConfig._local_locks.get(self.alias)
        if lock is None:
            lock = threading.RLock()
            DatabaseConfig._local_locks[self.alias] = lock
        return lock


    def integrity_check(self) -> bool:
        """Run PRAGMA integrity_check on the local database.

        Returns True if the result is 'ok', False otherwise or on error.
        """
        try:
            with self.open_ro_sqlite() as con:
                row = con.execute("PRAGMA integrity_check").fetchone()
            status = (row[0] if row else "").lower()
            return status == "ok"
        except Exception as e:
            logger.error(f"Integrity check error ({self.alias}): {e}")
            return False

    def open_ro_sqlite(self):
        uri = f"file:{self.path}?mode=ro"
        con = sql.connect(uri, uri=True, check_same_thread=False)
        con.execute("PRAGMA read_uncommitted=0;")
        con.execute("PRAGMA mmap_size=0;")
        con.execute("PRAGMA busy_timeout=250;")
        return con

    def sync(self):
        """Synchronize the local database with the remote Turso replica safely.
        Uses a cross-process nonblocking file lock so only one sync runs at a time,
        without blocking readers.
        """
        lockfile = f"{self.path}.sync.lock"
        with _sync_filelock(lockfile) as acquired:
            if not acquired:
                logger.debug("Sync skipped: another process is syncing.")
                return False
            with _SYNC_LOCK:  # keep thread safety inside this process
                self._dispose_local_connections()
                logger.debug("Disposing local connections and syncing database…")
                conn = None
                try:
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    conn = libsql.connect(self.path, sync_url=self.turso_url, auth_token=self.token)
                    conn.sync()
                except Exception as e:
                    logger.error(f"Database sync failed: {e}")
                    raise
                finally:
                    if conn is not None:
                        with suppress(Exception):
                            conn.close()
                            logger.info("Connection closed")

            update_time = datetime.now(timezone.utc)
            logger.info(f"Database synced at {update_time} UTC")

            ok = self.integrity_check()
            if not ok:
                logger.error("Post-sync integrity check failed.")

            if self.alias == "wcmkt2":
                validation_test = self.validate_sync() if ok else False
                st.session_state.sync_status = "Success" if validation_test else "Failed"
            st.session_state.sync_check = False
        return True

    def validate_sync(self)-> bool:
        alias = self.alias
        with self.remote_engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(last_update) FROM marketstats")).fetchone()
            remote_last_update = result[0]
            conn.close()
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(last_update) FROM marketstats")).fetchone()
            local_last_update = result[0]
            conn.close()
        logger.info("-"*40)
        logger.info(f"alias: {alias} validate_sync()")
        timestamp = datetime.now(timezone.utc)
        local_timestamp = datetime.now()
        logger.info(f"time: {local_timestamp.strftime('%Y-%m-%d %H:%M:%S')} (local); {timestamp.strftime('%Y-%m-%d %H:%M:%S')} (utc)")
        logger.info(f"remote_last_update: {remote_last_update}")
        logger.info(f"local_last_update: {local_last_update}")
        logger.info("-"*40)
        validation_test = remote_last_update == local_last_update
        logger.info(f"validation_test: {validation_test}")
        return validation_test

    def get_table_list(self, local_only: bool = True)-> list[tuple]:
        if local_only:
            engine = self.engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [table.name for table in tables if "sqlite" not in table.name]
                conn.close()
                return table_list
        else:
            engine = self.remote_engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [table.name for table in tables if "sqlite" not in table.name]
                conn.close()
                return table_list

    def get_table_columns(self, table_name: str, local_only: bool = True, full_info: bool = False) -> list[dict]:
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
                    column_info.append({
                    "cid": col.cid,
                    "name": col.name,
                    "type": col.type,
                    "notnull": col.notnull,
                    "dflt_value": col.dflt_value,
                    "pk": col.pk
                })
            else:
                column_info = [col.name for col in columns]
            conn.close()
            return column_info

    def get_most_recent_update(self, table_name: str, remote: bool = False)-> datetime:
        """
        Get the most recent update time for a specific table
        Args:
            table_name: str - The name of the table to get the most recent update time for
            remote: bool - If True, get the most recent update time from the remote database, if False, get the most recent update time from the local database

        Returns:
            The most recent update time for the table
        """
        engine = self.remote_engine if remote else self.engine
        session = Session(bind=engine)
        with session.begin():
            updates = select(UpdateLog.timestamp).where(UpdateLog.table_name == table_name).order_by(UpdateLog.timestamp.desc())
            result = session.execute(updates).fetchone()

            update_time = result[0] if result is not None else None
            update_time = update_time.replace(tzinfo=timezone.utc) if update_time is not None else None
        session.close()
        return update_time

    def get_time_since_update(self, table_name: str = "marketstats", remote: bool = False):
        status = self.get_most_recent_update(table_name, remote=remote)
        if status is None:
            logger.info("No update time available yet")
            return None
        now = datetime.now(timezone.utc)
        time_since = now - status
        logger.info(f"update_time: {status} utc")
        logger.info(f"time_since: {time_since}")
        return time_since if time_since is not None else None


if __name__ == "__main__":
    pass
