from sqlalchemy import create_engine, inspect, text, select, NullPool
from sqlalchemy.exc import NoSuchTableError, OperationalError
import streamlit as st
import os
import json

from logging_config import setup_logging
import sqlite3 as sql
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import threading
from contextlib import suppress
from time import perf_counter
from dataclasses import dataclass
import shutil
from pathlib import Path
import turso.sync as tursosync

logger = setup_logging(__name__)

# =============================================================================
# Doctrine Configuration Constants
# =============================================================================

# Default ship target stock level when not explicitly configured
DEFAULT_SHIP_TARGET = 20

# =============================================================================
# Database Configuration
# =============================================================================

# Global lock to serialize sync operations within the process
_SYNC_LOCK = threading.Lock()


@dataclass(frozen=True)
class SyncResult:
    """Outcome of DatabaseConfig.sync().

    ok: pull succeeded and post-sync integrity check passed.
    changed: pull applied new data (or a fresh bootstrap occurred).

    __bool__ preserves the legacy `if db.sync():` contract (truthy == ok).
    """

    ok: bool
    changed: bool

    def __bool__(self) -> bool:
        return self.ok


# Aliases currently serving restored backup data (value = restore time, UTC).
# Module-level: degraded-ness is a property of the on-disk file, i.e. process-wide.
_DEGRADED_REGISTRY: dict[str, datetime] = {}


def get_degraded_aliases() -> dict[str, datetime]:
    """Return a copy of {alias: restore_time} for DBs serving backup data."""
    return dict(_DEGRADED_REGISTRY)


def clear_degraded(alias: str) -> None:
    """Remove ``alias`` from the degraded registry (no-op if absent)."""
    _DEGRADED_REGISTRY.pop(alias, None)


def get_settings() -> dict:
    from settings_service import SettingsService

    return SettingsService().settings_dict


def _resolve_turso_section(
    alias: str,
    market_secret_keys: dict[str, str],
    turso_key_overrides: dict[str, str],
) -> str:
    """Return the secrets.toml section name holding ``alias``'s Turso creds.

    Resolution order (single source of truth first):
      1. Market hubs: the ``turso_secret_key`` their MarketConfig advertises in
         settings.toml ``[markets.*]`` — so the config the app reasons about and
         the config that drives sync can never drift.
      2. Utility DBs: a ``[db_turso_keys]`` override (e.g. sde -> sdelite_turso).
      3. Convention: ``{alias}_turso``.
    """
    return (
        market_secret_keys.get(alias)
        or turso_key_overrides.get(alias)
        or f"{alias}_turso"
    )


class DatabaseConfig:
    settings = get_settings()
    # master config variable for the database to use
    wcdbmap = settings["env_db_aliases"][settings["env"]["env"]]

    # Build database paths dynamically from settings.toml [db_paths]
    _db_paths = {alias: path for alias, path in settings["db_paths"].items()}

    _turso_key_overrides = settings.get("db_turso_keys", {})
    try:
        from settings_service import get_all_market_configs
        _market_secret_keys = {
            cfg.database_alias: cfg.turso_secret_key
            for cfg in get_all_market_configs().values()
        }
    except Exception as _exc:  # bad/missing [markets.*] — degrade, but make it visible
        logger.error("Failed to load market Turso secret keys: %s", _exc)
        _market_secret_keys = {}
    _db_turso_urls: dict[str, str] = {}
    _db_turso_auth_tokens: dict[str, str] = {}
    for _alias in _db_paths:
        _turso_key = f"{_alias}_turso"
        _secret_key = _resolve_turso_section(_alias, _market_secret_keys, _turso_key_overrides)
        try:
            _db_turso_urls[_turso_key] = st.secrets[_secret_key].url
            _db_turso_auth_tokens[_turso_key] = st.secrets[_secret_key].token
        except (KeyError, AttributeError):
            pass  # Not all aliases need Turso (graceful degradation)

    # Per-alias probe table for post-sync freshness validation.
    # Empty mapping means "skip the probe and trust libsql sync".
    _freshness_probes: dict[str, str] = settings.get("freshness_probes", {})

    # Shared handles per-alias to avoid multiple simultaneous connections to the same file
    _engines: dict[str, object] = {}
    _remote_engines: dict[str, object] = {}
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

    def __init__(self, alias: str, dialect: str = "sqlite+turso"):
        if alias == "wcmkt":
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
        self.probe_table = self._freshness_probes.get(self.alias)
        self._engine = None
        self._remote_engine = None
        self._sqlite_local_connect = None
        self._ro_engine = None

    @property
    def has_remote_credentials(self) -> bool:
        """Return True when Turso URL/token are available for this alias."""
        return bool(self.turso_url and self.token)

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

    def _replica_metadata_valid(self) -> bool:
        """True when {path}-info exists and parses as pyturso JSON metadata.

        A libsql-era or corrupt -info file fails the parse, which routes the
        replica through nuke + fresh bootstrap (deploy-day upgrade path).
        """
        info_path = Path(self.path + "-info")
        if not info_path.exists():
            return False
        try:
            json.loads(info_path.read_text())
            return True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False

    def _ensure_replica_consistency(self) -> None:
        """Enforce the .db/.db-info pairing invariant before any sync connect.

        Never pull on a db lacking valid metadata: a .db without (valid)
        -info, or an orphaned -info, is removed so pull() starts from a
        clean bootstrap. Both-absent is the normal cold-start case.
        """
        db_exists = os.path.exists(self.path)
        meta_valid = self._replica_metadata_valid()
        if db_exists and meta_valid:
            return
        if db_exists or os.path.exists(self.path + "-info"):
            logger.warning(
                f"Inconsistent replica state for {self.alias} "
                f"(db_exists={db_exists}, metadata_valid={meta_valid}); "
                "removing for fresh bootstrap"
            )
            self._remove_replica_files()

    def _pull_once(self) -> bool:
        """Open a sync connection, pull, checkpoint, close.

        Returns pull()'s changed flag. checkpoint() folds the WAL into the
        main file so snapshot_backup() copies a complete database.
        """
        sync_start = perf_counter()
        conn = tursosync.connect(
            self.path, remote_url=self.turso_url, auth_token=self.token
        )
        try:
            changed = conn.pull()
            conn.checkpoint()
        finally:
            with suppress(Exception):
                conn.close()
        sync_time = round((perf_counter() - sync_start) * 1000, 2)
        logger.info(
            f"pull completed for {self.alias} in {sync_time} ms "
            f"(changed={changed}) at "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return changed

    def sync(self) -> SyncResult:
        """Pull remote changes into the local replica safely.

        Serialized by _SYNC_LOCK with dispose-before-sync. Enforces the
        file-state machine, retries once via nuke + fresh bootstrap on
        integrity failure, snapshots a backup pair on success, and clears
        the degraded registry.

        Returns:
            SyncResult(ok, changed). Truthiness == ok, preserving the
            legacy bool contract. Callers own cache invalidation and UI.

        Raises:
            ValueError: missing Turso credentials for this alias.
            Exception: pull/network failures propagate (a healthy local
                file is never deleted on a network error).
        """
        if not self.turso_url or not self.token:
            raise ValueError(
                f"Missing Turso credentials for alias '{self.alias}'. "
                f"Add the matching section to .streamlit/secrets.toml"
            )
        logger.info("-" * 40)
        logger.info(
            f"sync() starting for {self.alias} (url={self.turso_url}) at "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        with _SYNC_LOCK:
            self._dispose_local_connections()
            self._ensure_replica_consistency()
            file_existed = os.path.exists(self.path)
            try:
                changed = self._pull_once()
            except Exception as e:
                logger.error(f"Database sync failed for {self.alias}: {e}")
                if not file_existed:
                    # connect() may create files before failing; don't leave
                    # an empty landmine that passes existence checks
                    self._remove_replica_files()
                raise
            changed = changed or not file_existed  # fresh bootstrap == new data

            ok = self.integrity_check()
            if not ok:
                logger.warning(
                    f"Post-sync integrity check failed for {self.alias}; "
                    "retrying with nuke + fresh bootstrap"
                )
                self._dispose_local_connections()
                self._remove_replica_files()
                changed = True
                try:
                    self._pull_once()
                except Exception:
                    logger.error(f"Retry pull failed for {self.alias}; removing partial replica")
                    self._remove_replica_files()
                    raise
                ok = self.integrity_check()

            if ok:
                self.snapshot_backup()  # best-effort; logs on failure
                clear_degraded(self.alias)
            else:
                logger.error(f"Fresh bootstrap for {self.alias} still fails integrity.")
            logger.info("-" * 40)
            return SyncResult(ok=ok, changed=changed)

    def _has_marketstats_table(self) -> bool:
        """Return True if the local database contains a ``marketstats`` table."""
        try:
            local_conn = sql.connect(f"file:{self.path}?mode=ro", uri=True)
            try:
                row = local_conn.execute(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type='table' AND name='marketstats'"
                ).fetchone()
                return row[0] > 0
            finally:
                local_conn.close()
        except Exception:
            return False

    def _update_log_cls(self):
        """Return the ``UpdateLog`` ORM class bound to this alias's ``Base``.

        Each database has its own ``DeclarativeBase`` registry, so the
        ``UpdateLog`` model lives alongside the rest of that database's
        models (e.g. ``models.UpdateLog`` for market DBs,
        ``build_cost_models.UpdateLog`` for build_cost).  Returns ``None``
        when no probe is configured for this alias.
        """
        if not self.probe_table:
            return None
        if self.alias == "build_cost":
            from build_cost_models import UpdateLog
            return UpdateLog
        from models import UpdateLog
        return UpdateLog

    def local_matches_remote(self) -> bool:
        """Check if local updatelog timestamp matches remote after sync.

        Probes the single ``updatelog`` row whose ``table_name`` matches
        ``self.probe_table`` (configured in ``settings.toml``
        ``[freshness_probes]``).  When no probe is configured for this
        alias the check is skipped and True is returned — sync is trusted
        as soon as libsql reports success.

        Returns True only when the probe is genuinely "not deployed yet":
        the remote ``updatelog`` table is missing, or it exists but has
        no row for this probe.  Returns False on local read failure or
        when local and remote timestamps differ.  Connection-class errors
        (auth, network, TLS, etc.) propagate to the caller so a real
        failure is surfaced instead of masked as "synced".
        """
        UpdateLog = self._update_log_cls()
        if UpdateLog is None:
            return True

        # Pre-check that the remote probe table exists.  Doing this via
        # the inspector means a missing table is a clean boolean signal
        # rather than a connection-class OperationalError, so we can let
        # auth/network failures from the actual query propagate naturally
        # without swallowing them through error-type guessing.
        if not inspect(self.remote_engine).has_table("updatelog"):
            logger.warning(
                f"local_matches_remote({self.alias}, probe={self.probe_table}): "
                "remote updatelog table absent; skipping freshness check"
            )
            return True

        stmt = select(UpdateLog.timestamp).where(
            UpdateLog.table_name == self.probe_table
        )

        with Session(self.remote_engine) as session:
            remote_ts = session.execute(stmt).scalar()

        if remote_ts is None:
            logger.warning(
                f"local_matches_remote({self.alias}, probe={self.probe_table}): "
                "no remote probe row yet; skipping freshness check"
            )
            return True

        # Local read fails closed: a missing table, malformed disk, or
        # any other DB error post-sync means sync didn't deliver usable
        # data, so the caller should resync.
        try:
            with Session(self.ro_engine) as session:
                local_ts = session.execute(stmt).scalar()
        except (OperationalError, NoSuchTableError) as e:
            logger.error(
                f"local_matches_remote({self.alias}) local read failed: {e}"
            )
            return False

        logger.info(
            f"local_matches_remote({self.alias}, probe={self.probe_table}): "
            f"remote={remote_ts}, local={local_ts}"
        )
        return remote_ts == local_ts

    def _remove_replica_files(self):
        """Remove the local db file and every pyturso/WAL sidecar artifact."""
        for suffix in ("", "-shm", "-wal", "-info", "-changes", "-wal-revert"):
            file_path = self.path + suffix
            if os.path.exists(file_path):
                with suppress(OSError):
                    os.remove(file_path)
                    logger.info(f"Removed replica artifact {file_path}")

    def snapshot_backup(self) -> bool:
        """Copy the live ``.db`` + ``.db-info`` pair to ``.bak`` files.

        Pure file copy — the caller (sync()) is responsible for having
        checkpointed the WAL first so the main file is complete. Each copy
        goes to a temp file then an atomic os.replace(), so a mid-copy crash
        cannot leave a torn backup. Best-effort: returns False on any error.
        """
        try:
            for src, dst in (
                (self.path, self.path + ".bak"),
                (self.path + "-info", self.path + "-info.bak"),
            ):
                tmp = dst + ".tmp"
                shutil.copy2(src, tmp)
                os.replace(tmp, dst)
            logger.info(f"snapshot_backup: wrote backup pair for {self.alias}")
            return True
        except OSError as e:
            logger.error(f"snapshot_backup failed for {self.alias}: {e}")
            return False

    def restore_from_backup(self) -> bool:
        """Replace the live replica with the last-known-good backup pair.

        Checks the backup pair exists BEFORE touching live files — a
        malformed live file is diagnostic evidence when no backup exists.
        The backup pair is first copied to ``.tmp`` staging files next to
        the live path; only once BOTH staged copies succeed are local
        connections disposed, the live replica files removed, and the
        staged files moved into place with ``os.replace()``. This keeps
        the live files completely untouched if staging fails partway
        (e.g. a disk error on the second copy), rather than leaving a
        torn replica (a ``.db`` with no matching ``-info`` sidecar)
        behind. On success, registers the alias in the degraded
        registry; a later successful sync() clears it (the restored
        pair is a valid replica, so the next pull() catches it up
        incrementally).
        """
        bak, info_bak = self.path + ".bak", self.path + "-info.bak"
        if not (os.path.exists(bak) and os.path.exists(info_bak)):
            logger.error(
                f"restore_from_backup({self.alias}): no backup pair; "
                "leaving live files untouched"
            )
            return False

        tmp_db, tmp_info = self.path + ".tmp", self.path + "-info.tmp"
        with _SYNC_LOCK:
            try:
                shutil.copy2(bak, tmp_db)
                shutil.copy2(info_bak, tmp_info)
            except OSError as e:
                logger.error(f"restore_from_backup({self.alias}) staging copy failed: {e}")
                for tmp in (tmp_db, tmp_info):
                    with suppress(OSError):
                        if os.path.exists(tmp):
                            os.remove(tmp)
                return False

            self._dispose_local_connections()
            self._remove_replica_files()
            os.replace(tmp_db, self.path)
            os.replace(tmp_info, self.path + "-info")

            if not self.integrity_check():
                logger.error(
                    f"restore_from_backup({self.alias}): restored copy failed integrity"
                )
                return False
            _DEGRADED_REGISTRY[self.alias] = datetime.now(timezone.utc)
            logger.warning(
                f"{self.alias} restored from backup taken before last failure; "
                "serving degraded data until next successful sync"
            )
            return True

    def get_table_list(self, local_only: bool = True) -> list[str]:
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

    def get_most_recent_update(
        self,
        table_name: str,
        update_log_cls,
        remote: bool = False,
    ) -> datetime | None:
        """Return the updatelog timestamp for ``table_name``, or None if absent.

        Args:
            table_name: Value to match against ``updatelog.table_name``.
            update_log_cls: ORM ``UpdateLog`` class bound to the correct
                ``Base``.  Callers pass the class from the module that
                owns this database's models (e.g. ``models.UpdateLog`` for
                market DBs, ``build_cost_models.UpdateLog`` for build_cost).
            remote: Read from the Turso remote engine when True.

        Returns the timestamp as a tz-aware UTC ``datetime``, or None when
        no row matches.  The column is stored as a naive datetime; UTC is
        the contract enforced by the backend writer.
        """
        engine = self.remote_engine if remote else self.engine
        with Session(bind=engine) as session:
            stmt = select(update_log_cls.timestamp).where(
                update_log_cls.table_name == table_name
            )
            update_time = session.execute(stmt).scalar()
        if update_time is None:
            return None
        return update_time.replace(tzinfo=timezone.utc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync a local database from Turso")
    parser.add_argument(
        "alias",
        nargs="?",
        default="wcmktprod",
        help="Database alias from settings.toml [db_paths] (default: wcmktprod)",
    )
    args = parser.parse_args()

    db = DatabaseConfig(args.alias)
    print(f"Syncing '{args.alias}' from {db.turso_url} ...")
    ok = db.sync()
    print(f"Sync {'succeeded' if ok else 'FAILED'} (integrity check: {'ok' if ok else 'FAIL'})")
