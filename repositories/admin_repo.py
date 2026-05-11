"""Write-capable repository for admin watchlist operations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from config import DatabaseConfig
from logging_config import setup_logging
from repositories.base import BaseRepository
from settings_service import SettingsService, resolve_db_alias

logger = setup_logging(__name__, log_file="admin_repo.log")

WATCHLIST_COLUMNS = [
    "type_id",
    "group_id",
    "type_name",
    "group_name",
    "category_id",
    "category_name",
]


class AdminRepository:
    """Repository for reading and replacing the watchlist table."""

    def __init__(self, db: DatabaseConfig, *, write_target: str = "local"):
        self._db = db
        self._write_target = write_target
        self._reader = BaseRepository(db, logger)

    @classmethod
    def from_sqlite_path(cls, path: str | Path) -> "AdminRepository":
        """Create a repository backed by an explicit SQLite file for tests."""
        engine = create_engine(f"sqlite:///{path}")
        return cls._from_engine(engine)

    @classmethod
    def _from_engine(cls, engine) -> "AdminRepository":
        repo = cls.__new__(cls)
        repo._db = None
        repo._write_target = "local"
        repo._reader = None
        repo._engine_override = engine
        return repo

    def get_watchlist(self) -> pd.DataFrame:
        """Return the current watchlist rows ordered by type_id."""
        query = text(
            """
            SELECT type_id, group_id, type_name, group_name, category_id, category_name
            FROM watchlist
            ORDER BY type_id
            """
        )
        if getattr(self, "_reader", None) is not None:
            return self._reader.read_df(query).reset_index(drop=True)

        with self._get_write_engine().connect() as conn:
            return pd.read_sql_query(query, conn).reset_index(drop=True)

    def replace_watchlist(self, rows: list[dict]) -> None:
        """Replace the entire watchlist table inside one transaction."""
        engine = self._get_write_engine()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM watchlist"))
            for row in rows:
                conn.execute(
                    text(
                        """
                        INSERT INTO watchlist (
                            type_id,
                            group_id,
                            type_name,
                            group_name,
                            category_id,
                            category_name
                        ) VALUES (
                            :type_id,
                            :group_id,
                            :type_name,
                            :group_name,
                            :category_id,
                            :category_name
                        )
                        """
                    ),
                    row,
                )

    def _get_write_engine(self):
        override = getattr(self, "_engine_override", None)
        if override is not None:
            return override
        if self._write_target == "remote":
            return self._db.remote_engine
        return self._db.engine


def get_admin_repository(db_alias: str | None = None) -> AdminRepository:
    """Return an admin repository for the active market database."""
    settings = SettingsService()
    resolved_alias = resolve_db_alias(db_alias)
    db = DatabaseConfig(resolved_alias)
    return AdminRepository(db, write_target=settings.admin_write_target)
