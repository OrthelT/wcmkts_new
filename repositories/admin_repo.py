"""Write-capable repository for admin watchlist operations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import DatabaseConfig
from logging_config import setup_logging
from models import Watchlist
from repositories.base import BaseRepository
from settings_service import SettingsService, resolve_db_alias

logger = setup_logging(__name__, log_file="admin_repo.log")

# Static-typing alias: every code path that selects a write target must agree on
# these two strings. Runtime guard (``_normalize_write_target``) catches deploy-
# config typos; Literal catches in-source typos at type-check time.
WriteTarget = Literal["local", "remote"]

WATCHLIST_COLUMNS = [
    "type_id",
    "group_id",
    "type_name",
    "group_name",
    "category_id",
    "category_name",
]

DOCTRINE_FIT_OPTION_COLUMNS = [
    "doctrine_id",
    "doctrine_name",
    "fit_id",
    "fit_name",
    "ship_type_id",
    "ship_name",
    "target",
    "market_flag",
]

DOCTRINE_OPTION_COLUMNS = [
    "doctrine_id",
    "doctrine_name",
]


DOCTRINE_COLUMNS = [
    "fit_id",
    "ship_id",
    "ship_name",
    "hulls",
    "type_id",
    "type_name",
    "fit_qty",
    "fits_on_mkt",
    "total_stock",
    "price",
    "avg_vol",
    "days",
    "group_id",
    "group_name",
    "category_id",
    "category_name",
    "timestamp",
]

ADMIN_WRITE_TARGETS = {"local", "remote"}


class AdminRepository:
    """Read + replace watchlist/doctrine tables. Multi-statement writes use ``engine.begin()`` for atomicity (libSQL wraps as a remote transaction; verify multi-statement changes against Turso staging)."""

    def __init__(self, db: DatabaseConfig, *, write_target: WriteTarget = "local"):
        self._db = db
        self._write_target = self._normalize_write_target(write_target)
        self._reader = BaseRepository(db, logger)

    @property
    def write_target(self) -> WriteTarget:
        """Return the normalized write target ('local' or 'remote')."""
        return self._write_target

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
            return self._reader.read_df(query, local=self._read_local()).reset_index(drop=True)

        with self._get_write_engine().connect() as conn:
            return pd.read_sql_query(query, conn).reset_index(drop=True)

    def replace_watchlist(self, rows: list[dict]) -> None:
        """Replace the entire watchlist table inside one transaction."""
        if not rows:
            raise ValueError("Refusing to replace watchlist with an empty watchlist")

        engine = self._get_write_engine()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM watchlist"))
            for index in range(0, len(rows), 500):
                conn.execute(sqlite_insert(Watchlist).values(rows[index : index + 500]))

    def get_doctrine_fit(self, doctrine_id: int, fit_id: int) -> dict | None:
        """Return a doctrine fit mapping for an existing doctrine/fit pair."""
        query = text(
            """
            SELECT doctrine_id, doctrine_name, fit_id, fit_name, ship_type_id,
                   ship_name, target, market_flag, friendly_name
            FROM doctrine_fits
            WHERE doctrine_id = :doctrine_id AND fit_id = :fit_id
            LIMIT 1
            """
        )
        with self._get_write_engine().connect() as conn:
            row = conn.execute(query, {"doctrine_id": doctrine_id, "fit_id": fit_id}).mappings().first()
        return dict(row) if row else None

    def get_doctrine_name(self, doctrine_id: int) -> str | None:
        """Return the display name for an existing doctrine id."""
        query = text(
            """
            SELECT doctrine_name
            FROM doctrine_fits
            WHERE doctrine_id = :doctrine_id
              AND doctrine_name IS NOT NULL
            ORDER BY fit_id
            LIMIT 1
            """
        )
        with self._get_write_engine().connect() as conn:
            row = conn.execute(query, {"doctrine_id": doctrine_id}).first()
        return str(row[0]) if row and row[0] else None

    def doctrine_id_exists(self, doctrine_id: int) -> bool:
        """Return whether a doctrine_id is already registered."""
        query = text("SELECT 1 FROM doctrine_fits WHERE doctrine_id = :doctrine_id LIMIT 1")
        with self._get_write_engine().connect() as conn:
            return conn.execute(query, {"doctrine_id": doctrine_id}).first() is not None

    def doctrine_name_exists(self, doctrine_name: str) -> bool:
        """Return whether a normalized doctrine name is already registered."""
        query = text(
            """
            SELECT 1
            FROM doctrine_fits
            WHERE doctrine_name IS NOT NULL
              AND LOWER(TRIM(doctrine_name)) = LOWER(TRIM(:doctrine_name))
            LIMIT 1
            """
        )
        with self._get_write_engine().connect() as conn:
            return conn.execute(query, {"doctrine_name": doctrine_name}).first() is not None

    def doctrine_fit_id_exists(self, fit_id: int) -> bool:
        """Return whether a fit_id is already used by any doctrine fit."""
        query = text("SELECT 1 FROM doctrine_fits WHERE fit_id = :fit_id LIMIT 1")
        with self._get_write_engine().connect() as conn:
            return conn.execute(query, {"fit_id": fit_id}).first() is not None

    def get_next_doctrine_id(self) -> int:
        """Return the next available doctrine id."""
        query = text("SELECT COALESCE(MAX(doctrine_id), 0) + 1 FROM doctrine_fits")
        self._prepare_local_write()
        with self._get_write_engine().connect() as conn:
            return int(conn.execute(query).scalar_one())

    def get_next_doctrine_fit_id(self) -> int:
        """Return the next available doctrine fit id."""
        query = text("SELECT COALESCE(MAX(fit_id), 0) + 1 FROM doctrine_fits")
        self._prepare_local_write()
        with self._get_write_engine().connect() as conn:
            return int(conn.execute(query).scalar_one())

    def get_doctrine_options(self) -> pd.DataFrame:
        """Return current doctrine metadata for admin selectors."""
        query = text(
            """
            SELECT DISTINCT doctrine_id, doctrine_name
            FROM doctrine_fits
            WHERE doctrine_id IS NOT NULL
              AND doctrine_name IS NOT NULL
              AND TRIM(doctrine_name) != ''
            ORDER BY doctrine_name, doctrine_id
            """
        )
        if getattr(self, "_reader", None) is not None:
            return self._reader.read_df(query, local=self._read_local()).reset_index(drop=True)
        with self._get_write_engine().connect() as conn:
            return pd.read_sql_query(query, conn).reset_index(drop=True)

    def get_doctrine_fit_options(self) -> pd.DataFrame:
        """Return current doctrine and fit metadata for admin selectors."""
        query = text(
            """
            SELECT
                doctrine_id,
                doctrine_name,
                fit_id,
                fit_name,
                ship_type_id,
                ship_name,
                target,
                market_flag
            FROM doctrine_fits
            WHERE fit_id IS NOT NULL
            ORDER BY doctrine_name, fit_name, fit_id
            """
        )
        if getattr(self, "_reader", None) is not None:
            return self._reader.read_df(query, local=self._read_local()).reset_index(drop=True)
        with self._get_write_engine().connect() as conn:
            return pd.read_sql_query(query, conn).reset_index(drop=True)

    def create_doctrine(self, *, doctrine_id: int, doctrine_name: str) -> None:
        """Register a doctrine before it has any fits."""
        self._prepare_local_write()
        doctrine_name = doctrine_name.strip()
        if not doctrine_name:
            raise ValueError("doctrine_name must be a non-empty string")
        engine = self._get_write_engine()
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM doctrine_fits WHERE doctrine_id = :doctrine_id LIMIT 1"),
                {"doctrine_id": doctrine_id},
            ).first()
            if exists:
                raise ValueError(f"doctrine_id {doctrine_id} already exists")
            duplicate_name = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM doctrine_fits
                    WHERE doctrine_name IS NOT NULL
                      AND LOWER(TRIM(doctrine_name)) = LOWER(TRIM(:doctrine_name))
                    LIMIT 1
                    """
                ),
                {"doctrine_name": doctrine_name},
            ).first()
            if duplicate_name:
                raise ValueError("doctrine_name already exists")
            self._ensure_empty_doctrine_placeholder(conn, doctrine_id, doctrine_name)

    def rename_doctrine(self, *, doctrine_id: int, doctrine_name: str) -> None:
        """Rename a doctrine across tables that duplicate the raw doctrine name."""
        self._prepare_local_write()
        doctrine_id = int(doctrine_id)
        doctrine_name = doctrine_name.strip()
        if not doctrine_name:
            raise ValueError("doctrine_name must be a non-empty string")
        engine = self._get_write_engine()
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM doctrine_fits WHERE doctrine_id = :doctrine_id LIMIT 1"),
                {"doctrine_id": doctrine_id},
            ).first()
            if exists is None:
                raise ValueError(f"No doctrine found for doctrine_id={doctrine_id}")
            duplicate_name = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM doctrine_fits
                    WHERE doctrine_name IS NOT NULL
                      AND LOWER(TRIM(doctrine_name)) = LOWER(TRIM(:doctrine_name))
                      AND (doctrine_id IS NULL OR doctrine_id != :doctrine_id)
                    LIMIT 1
                    """
                ),
                {"doctrine_id": doctrine_id, "doctrine_name": doctrine_name},
            ).first()
            if duplicate_name:
                raise ValueError("doctrine_name already exists")
            conn.execute(
                text(
                    """
                    UPDATE doctrine_fits
                    SET doctrine_name = :doctrine_name
                    WHERE doctrine_id = :doctrine_id
                    """
                ),
                {"doctrine_id": doctrine_id, "doctrine_name": doctrine_name},
            )
            conn.execute(
                text(
                    """
                    UPDATE lead_ships
                    SET doctrine_name = :doctrine_name
                    WHERE doctrine_id = :doctrine_id
                    """
                ),
                {"doctrine_id": doctrine_id, "doctrine_name": doctrine_name},
            )

    def get_doctrine_fit_eft(self, fit_id: int) -> str:
        """Return the current fit as a simple EFT-style text block."""
        fit_query = text(
            """
            SELECT fit_name, ship_name
            FROM doctrine_fits
            WHERE fit_id = :fit_id
            LIMIT 1
            """
        )
        items_query = text(
            """
            SELECT type_id, type_name, fit_qty, ship_id
            FROM doctrines
            WHERE fit_id = :fit_id
            ORDER BY id
            """
        )
        params = {"fit_id": fit_id}
        if getattr(self, "_reader", None) is not None:
            fit_df = self._reader.read_df(fit_query, params=params, local=self._read_local())
            items_df = self._reader.read_df(items_query, params=params, local=self._read_local())
            if fit_df.empty:
                return ""
            fit = fit_df.iloc[0].to_dict()
            items = items_df.to_dict(orient="records")
        else:
            with self._get_write_engine().connect() as conn:
                fit = conn.execute(fit_query, params).mappings().first()
                items = conn.execute(items_query, params).mappings().all()
        if fit is None:
            return ""
        ship_name = str(fit["ship_name"] or "").strip()
        fit_name = str(fit["fit_name"] or "").strip()
        lines = [f"[{ship_name}, {fit_name}]"]
        for item in items:
            if int(item["type_id"]) == int(item["ship_id"]):
                continue
            quantity = int(item["fit_qty"] or 1)
            type_name = str(item["type_name"]).strip()
            lines.append(f"{type_name} x{quantity}" if quantity > 1 else type_name)
        return "\n".join(lines)

    def save_doctrine_fit(
        self,
        *,
        doctrine_id: int,
        doctrine_name: str,
        fit_id: int,
        fit_name: str,
        ship_name: str,
        item_quantities: dict[str, int],
        target: int,
        market_flag: str,
        mode: str,
    ) -> None:
        """Add or update one fit in an existing doctrine and rebuild derived rows."""
        if mode not in {"add", "update"}:
            raise ValueError("mode must be add or update")
        if not item_quantities:
            raise ValueError("Doctrine fit must contain at least one fitted item")

        ship = self._resolve_type_metadata(ship_name)
        items = [self._resolve_type_metadata(name) | {"fit_qty": qty} for name, qty in item_quantities.items()]
        timestamp = datetime.now(UTC).isoformat()

        self._prepare_local_write()
        engine = self._get_write_engine()
        with engine.begin() as conn:
            market_stats = self._get_market_stats(conn, [ship["type_id"], *[item["type_id"] for item in items]])
            hull_stock = int(market_stats.get(ship["type_id"], {}).get("total_stock", 0))

            existing_fit = conn.execute(
                text(
                    """
                    SELECT id
                    FROM doctrine_fits
                    WHERE doctrine_id = :doctrine_id AND fit_id = :fit_id
                    LIMIT 1
                    """
                ),
                {"doctrine_id": doctrine_id, "fit_id": fit_id},
            ).first()
            if mode == "add" and existing_fit is None:
                # Invariant: an "add" must not collide with an existing fit_id
                # under a different doctrine. Two concurrent transactional adds
                # computing the same MAX(fit_id)+1 would otherwise both succeed.
                fit_id_conflict = conn.execute(
                    text("SELECT 1 FROM doctrine_fits WHERE fit_id = :fit_id LIMIT 1"),
                    {"fit_id": fit_id},
                ).first()
                if fit_id_conflict:
                    raise ValueError(
                        f"fit_id {fit_id} already exists under a different doctrine"
                    )
            fit_values = {
                "doctrine_name": doctrine_name,
                "fit_name": fit_name,
                "ship_type_id": ship["type_id"],
                "doctrine_id": doctrine_id,
                "fit_id": fit_id,
                "ship_name": ship["type_name"],
                "target": target,
                "market_flag": market_flag,
            }
            if existing_fit:
                conn.execute(
                    text(
                        """
                        UPDATE doctrine_fits
                        SET doctrine_name = :doctrine_name,
                            fit_name = :fit_name,
                            ship_type_id = :ship_type_id,
                            ship_name = :ship_name,
                            target = :target,
                            market_flag = :market_flag
                        WHERE doctrine_id = :doctrine_id AND fit_id = :fit_id
                        """
                    ),
                    fit_values,
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO doctrine_fits
                            (
                                doctrine_name, fit_name, ship_type_id, doctrine_id,
                                fit_id, ship_name, target, market_flag
                            )
                        VALUES
                            (
                                :doctrine_name, :fit_name, :ship_type_id, :doctrine_id,
                                :fit_id, :ship_name, :target, :market_flag
                            )
                        """
                    ),
                    fit_values,
                )

            self._delete_empty_doctrine_placeholders(conn, doctrine_id)
            conn.execute(text("DELETE FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
            conn.execute(
                text(
                    """
                    INSERT INTO ship_targets
                        (fit_id, fit_name, ship_id, ship_name, ship_target, created_at)
                    VALUES
                        (:fit_id, :fit_name, :ship_id, :ship_name, :ship_target, :created_at)
                    """
                ),
                {
                    "fit_id": fit_id,
                    "fit_name": fit_name,
                    "ship_id": ship["type_id"],
                    "ship_name": ship["type_name"],
                    "ship_target": target,
                    "created_at": timestamp,
                },
            )
            self._ensure_doctrine_map(conn, doctrine_id, fit_id)
            self._ensure_lead_ship(conn, doctrine_id, doctrine_name, fit_id, ship["type_id"])
            conn.execute(text("DELETE FROM doctrines WHERE fit_id = :fit_id"), {"fit_id": fit_id})
            doctrine_rows = [
                self._build_doctrine_row(
                    type_meta=ship | {"fit_qty": 1},
                    fit_id=fit_id,
                    ship=ship,
                    hull_stock=hull_stock,
                    market_stats=market_stats,
                    timestamp=timestamp,
                )
            ]
            doctrine_rows.extend(
                self._build_doctrine_row(
                    type_meta=item,
                    fit_id=fit_id,
                    ship=ship,
                    hull_stock=hull_stock,
                    market_stats=market_stats,
                    timestamp=timestamp,
                )
                for item in items
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO doctrines ({", ".join(DOCTRINE_COLUMNS)})
                    VALUES ({", ".join(f":{column}" for column in DOCTRINE_COLUMNS)})
                    """
                ),
                doctrine_rows,
            )
            self._add_doctrine_types_to_watchlist(conn, [ship, *items])

    def delete_doctrine_fit(self, *, doctrine_id: int, fit_id: int) -> None:
        """Delete one doctrine fit and clean all linked derived rows."""
        self._prepare_local_write()
        engine = self._get_write_engine()
        with engine.begin() as conn:
            existing_fit = conn.execute(
                text(
                    """
                    SELECT doctrine_name, fit_id
                    FROM doctrine_fits
                    WHERE doctrine_id = :doctrine_id AND fit_id = :fit_id
                    LIMIT 1
                    """
                ),
                {"doctrine_id": doctrine_id, "fit_id": fit_id},
            ).mappings().first()
            if existing_fit is None:
                raise ValueError(f"No doctrine fit found for doctrine_id={doctrine_id}, fit_id={fit_id}")

            doctrine_name = str(existing_fit["doctrine_name"] or "").strip()
            conn.execute(
                text("DELETE FROM doctrine_fits WHERE doctrine_id = :doctrine_id AND fit_id = :fit_id"),
                {"doctrine_id": doctrine_id, "fit_id": fit_id},
            )
            conn.execute(text("DELETE FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
            conn.execute(
                text("DELETE FROM doctrine_map WHERE doctrine_id = :doctrine_id AND fitting_id = :fit_id"),
                {"doctrine_id": doctrine_id, "fit_id": fit_id},
            )
            conn.execute(text("DELETE FROM doctrines WHERE fit_id = :fit_id"), {"fit_id": fit_id})

            remaining_fit = conn.execute(
                text(
                    """
                    SELECT doctrine_name, fit_id, ship_type_id
                    FROM doctrine_fits
                    WHERE doctrine_id = :doctrine_id
                      AND fit_id IS NOT NULL
                    ORDER BY fit_id
                    LIMIT 1
                    """
                ),
                {"doctrine_id": doctrine_id},
            ).mappings().first()

            if remaining_fit is None:
                conn.execute(
                    text("DELETE FROM lead_ships WHERE doctrine_id = :doctrine_id"),
                    {"doctrine_id": doctrine_id},
                )
                self._ensure_empty_doctrine_placeholder(conn, doctrine_id, doctrine_name)
                return

            self._delete_empty_doctrine_placeholders(conn, doctrine_id)
            replacement_name = str(remaining_fit["doctrine_name"] or doctrine_name)
            replacement_fit_id = int(remaining_fit["fit_id"])
            replacement_ship_id = int(remaining_fit["ship_type_id"])
            lead_ship = conn.execute(
                text("SELECT fit_id FROM lead_ships WHERE doctrine_id = :doctrine_id LIMIT 1"),
                {"doctrine_id": doctrine_id},
            ).mappings().first()
            if lead_ship is None:
                self._ensure_lead_ship(
                    conn,
                    doctrine_id,
                    replacement_name,
                    replacement_fit_id,
                    replacement_ship_id,
                )
            elif int(lead_ship["fit_id"] or -1) == fit_id:
                conn.execute(
                    text(
                        """
                        UPDATE lead_ships
                        SET doctrine_name = :doctrine_name,
                            lead_ship = :lead_ship,
                            fit_id = :fit_id
                        WHERE doctrine_id = :doctrine_id
                        """
                    ),
                    {
                        "doctrine_name": replacement_name,
                        "lead_ship": replacement_ship_id,
                        "fit_id": replacement_fit_id,
                        "doctrine_id": doctrine_id,
                    },
                )

    def _resolve_type_metadata(self, type_name: str) -> dict:
        # Case-sensitive on purpose: EVE type names occasionally differ only by
        # case (rare today, but COLLATE NOCASE + LIMIT 1 would silently pick an
        # arbitrary row). Per the project no-wrong-data rule, fail loud.
        query = text(
            """
            SELECT typeID AS type_id, typeName AS type_name, groupID AS group_id,
                   groupName AS group_name, categoryID AS category_id, categoryName AS category_name
            FROM inv_info
            WHERE typeName = :type_name
            LIMIT 1
            """
        )
        with self._get_sde_engine().connect() as conn:
            row = conn.execute(query, {"type_name": type_name.strip()}).mappings().first()
        if row is None:
            raise ValueError(f"Unknown EVE type: {type_name}")
        return {
            "type_id": int(row["type_id"]),
            "type_name": str(row["type_name"]),
            "group_id": int(row["group_id"]),
            "group_name": str(row["group_name"]),
            "category_id": int(row["category_id"]),
            "category_name": str(row["category_name"]),
        }

    def _get_market_stats(self, conn, type_ids: list[int]) -> dict[int, dict]:
        if not type_ids:
            return {}
        placeholders = ", ".join(f":type_id_{index}" for index in range(len(type_ids)))
        params = {f"type_id_{index}": type_id for index, type_id in enumerate(type_ids)}
        rows = conn.execute(
            text(
                f"""
                SELECT type_id, total_volume_remain, price, avg_volume, days_remaining
                FROM marketstats
                WHERE type_id IN ({placeholders})
                """
            ),
            params,
        ).mappings()
        return {
            int(row["type_id"]): {
                "total_stock": int(row["total_volume_remain"] or 0),
                "price": float(row["price"] or 0),
                "avg_vol": float(row["avg_volume"] or 0),
                "days": float(row["days_remaining"] or 0),
            }
            for row in rows
        }

    def _build_doctrine_row(
        self,
        *,
        type_meta: dict,
        fit_id: int,
        ship: dict,
        hull_stock: int,
        market_stats: dict[int, dict],
        timestamp: str,
    ) -> dict:
        stats = market_stats.get(type_meta["type_id"], {})
        fit_qty = int(type_meta["fit_qty"])
        total_stock = int(stats.get("total_stock", 0))
        return {
            "fit_id": fit_id,
            "ship_id": ship["type_id"],
            "ship_name": ship["type_name"],
            "hulls": hull_stock,
            "type_id": type_meta["type_id"],
            "type_name": type_meta["type_name"],
            "fit_qty": fit_qty,
            "fits_on_mkt": total_stock // fit_qty if fit_qty else 0,
            "total_stock": total_stock,
            "price": float(stats.get("price", 0)),
            "avg_vol": float(stats.get("avg_vol", 0)),
            "days": float(stats.get("days", 0)),
            "group_id": type_meta["group_id"],
            "group_name": type_meta["group_name"],
            "category_id": type_meta["category_id"],
            "category_name": type_meta["category_name"],
            "timestamp": timestamp,
        }

    def _ensure_doctrine_map(self, conn, doctrine_id: int, fit_id: int) -> None:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM doctrine_map
                WHERE doctrine_id = :doctrine_id AND fitting_id = :fit_id
                LIMIT 1
                """
            ),
            {"doctrine_id": doctrine_id, "fit_id": fit_id},
        ).first()
        if exists:
            return
        next_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM doctrine_map")).scalar_one()
        conn.execute(
            text(
                """
                INSERT INTO doctrine_map (id, doctrine_id, fitting_id)
                VALUES (:id, :doctrine_id, :fit_id)
                """
            ),
            {"id": next_id, "doctrine_id": doctrine_id, "fit_id": fit_id},
        )

    def _ensure_empty_doctrine_placeholder(
        self,
        conn,
        doctrine_id: int,
        doctrine_name: str,
    ) -> None:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM doctrine_fits
                WHERE doctrine_id = :doctrine_id AND fit_id IS NULL
                LIMIT 1
                """
            ),
            {"doctrine_id": doctrine_id},
        ).first()
        if exists:
            return
        conn.execute(
            text(
                """
                INSERT INTO doctrine_fits (doctrine_name, doctrine_id)
                VALUES (:doctrine_name, :doctrine_id)
                """
            ),
            {"doctrine_name": doctrine_name, "doctrine_id": doctrine_id},
        )

    def _delete_empty_doctrine_placeholders(self, conn, doctrine_id: int) -> None:
        conn.execute(
            text("DELETE FROM doctrine_fits WHERE doctrine_id = :doctrine_id AND fit_id IS NULL"),
            {"doctrine_id": doctrine_id},
        )

    def _ensure_lead_ship(
        self,
        conn,
        doctrine_id: int,
        doctrine_name: str,
        fit_id: int,
        ship_type_id: int,
    ) -> None:
        existing = conn.execute(
            text("SELECT fit_id FROM lead_ships WHERE doctrine_id = :doctrine_id LIMIT 1"),
            {"doctrine_id": doctrine_id},
        ).mappings().first()
        if existing:
            if int(existing["fit_id"] or -1) == fit_id:
                conn.execute(
                    text(
                        """
                        UPDATE lead_ships
                        SET doctrine_name = :doctrine_name,
                            lead_ship = :lead_ship,
                            fit_id = :fit_id
                        WHERE doctrine_id = :doctrine_id AND fit_id = :fit_id
                        """
                    ),
                    {
                        "doctrine_name": doctrine_name,
                        "doctrine_id": doctrine_id,
                        "lead_ship": ship_type_id,
                        "fit_id": fit_id,
                    },
                )
            return
        conn.execute(
            text(
                """
                INSERT INTO lead_ships (doctrine_name, doctrine_id, lead_ship, fit_id)
                VALUES (:doctrine_name, :doctrine_id, :lead_ship, :fit_id)
                """
            ),
            {
                "doctrine_name": doctrine_name,
                "doctrine_id": doctrine_id,
                "lead_ship": ship_type_id,
                "fit_id": fit_id,
            },
        )

    def _add_doctrine_types_to_watchlist(self, conn, types: list[dict]) -> None:
        rows = [
            {
                "type_id": item["type_id"],
                "group_id": item["group_id"],
                "type_name": item["type_name"],
                "group_name": item["group_name"],
                "category_id": item["category_id"],
                "category_name": item["category_name"],
            }
            for item in types
        ]
        if rows:
            conn.execute(
                sqlite_insert(Watchlist).values(rows).on_conflict_do_nothing(index_elements=["type_id"])
            )

    def _get_write_engine(self):
        override = getattr(self, "_engine_override", None)
        if override is not None:
            return override
        if self._write_target == "remote":
            return self._db.remote_engine
        return self._db.engine

    def _read_local(self) -> bool:
        return self._write_target != "remote"

    @staticmethod
    def _normalize_write_target(write_target: str) -> str:
        target = str(write_target).strip().lower()
        if target not in ADMIN_WRITE_TARGETS:
            raise ValueError("write_target must be 'local' or 'remote'")
        return target

    def _prepare_local_write(self) -> None:
        """Close stale local handles before local admin writes."""
        if getattr(self, "_engine_override", None) is not None:
            return
        if self._write_target != "local":
            return
        dispose = getattr(self._db, "_dispose_local_connections", None)
        if dispose is not None:
            dispose()

    def _get_sde_engine(self):
        override = getattr(self, "_engine_override", None)
        if override is not None:
            return override
        return DatabaseConfig("sde").engine


def get_admin_repository(db_alias: str | None = None) -> AdminRepository:
    """Return an admin repository for the active market database."""
    settings = SettingsService()
    resolved_alias = resolve_db_alias(db_alias)
    db = DatabaseConfig(resolved_alias)
    return AdminRepository(db, write_target=settings.admin_write_target)
