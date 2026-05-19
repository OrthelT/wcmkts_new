"""Admin service for guarded watchlist and doctrine edits."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

import pandas as pd

from logging_config import setup_logging
from repositories.admin_repo import WATCHLIST_COLUMNS, get_admin_repository
from services.eft_parser_service import parse_eft_fit
from services.eve_sso_service import get_eve_sso_service

# Deliberate exception to the services→state/ layering rule. The only consumers
# of AdminService are Streamlit admin pages, so the transitive Streamlit import
# is paid by callers who already depend on Streamlit. Avoiding this would mean
# injecting a cache-invalidator callable through every callsite of
# get_admin_service(), which added more complexity than it removed. Tests can
# still override via the constructor's `cache_invalidator` parameter.
from state.market_state import refresh_market_caches

# Static-typing aliases for the small set of admin-write enums. Runtime guards
# below still validate the actual values; Literal catches in-source typos.
MarketFlag = Literal["primary", "deployment", "both"]
SaveMode = Literal["add", "update"]


class AdminWriteIntegrityError(Exception):
    """Raised when a multi-statement admin write completes but read-back disagrees.

    Catches the scenario where a libsql write appears to succeed (the
    ``engine.begin()`` block exits without raising) but a later read shows
    the change did not take effect — e.g. a network drop after the SQL was
    sent but before the commit response was received, or a silent rollback.
    The admin sees a distinct error rather than a deceptive success +
    invisible partial state.
    """

logger = setup_logging(__name__, log_file="admin_service.log")


class AdminService:
    """Validate and persist authenticated admin edits."""

    def __init__(self, repository, auth_service, *, cache_invalidator=refresh_market_caches):
        self._repository = repository
        self._auth_service = auth_service
        self._cache_invalidator = cache_invalidator

    def get_watchlist(self) -> pd.DataFrame:
        """Return the current watchlist."""
        return self._repository.get_watchlist()

    def get_doctrine_options(self) -> pd.DataFrame:
        """Return current doctrine metadata for admin selectors."""
        return self._repository.get_doctrine_options()

    def get_doctrine_fit_options(self) -> pd.DataFrame:
        """Return current doctrine and fit metadata for admin selectors."""
        return self._repository.get_doctrine_fit_options()

    def get_doctrine_fit_eft(self, fit_id: int) -> str:
        """Return the current fit as an EFT-style text block."""
        return self._repository.get_doctrine_fit_eft(int(fit_id))

    def save_watchlist(self, watchlist_df: pd.DataFrame, *, signed_identity: dict | None) -> dict:
        """Validate and replace the watchlist table for the active market."""
        payload = self._require_admin(signed_identity)
        rows = self._normalize_rows(watchlist_df)
        self._validate_rows(rows)

        before_df = self._repository.get_watchlist()
        before_ids = {int(tid) for tid in before_df["type_id"].tolist()} if not before_df.empty else set()
        after_ids = {row["type_id"] for row in rows}
        added_type_ids = sorted(after_ids - before_ids)
        removed_type_ids = sorted(before_ids - after_ids)

        self._repository.replace_watchlist(rows)

        # Read-back verification: confirm the write actually committed by
        # reading the row count. If it disagrees, raise BEFORE invalidating
        # caches — otherwise the UI happily renders the stale (correct!) cache
        # and the user never notices the write was lost.
        actual_df = self._repository.get_watchlist()
        actual_count = 0 if actual_df.empty else len(actual_df)
        if actual_count != len(rows):
            raise AdminWriteIntegrityError(
                f"save_watchlist read-back mismatch: wrote {len(rows)} rows but "
                f"read-back found {actual_count}"
            )

        self._cache_invalidator()

        character_id = int(payload["character_id"])
        character_name = payload.get("character_name", "")
        logger.info(
            "watchlist_saved character_id=%s character_name=%s write_target=%s "
            "before=%d after=%d added=%s removed=%s",
            character_id,
            character_name,
            self._repository.write_target,
            len(before_ids),
            len(after_ids),
            added_type_ids,
            removed_type_ids,
        )

        return {
            "row_count": len(rows),
            "character_id": character_id,
            "added_type_ids": added_type_ids,
            "removed_type_ids": removed_type_ids,
        }

    def create_doctrine(self, *, doctrine_name: str, signed_identity: dict | None) -> dict:
        """Create an empty doctrine that can receive fits later."""
        payload = self._require_admin(signed_identity)
        doctrine_name = doctrine_name.strip()
        if not doctrine_name:
            raise ValueError("doctrine_name must be a non-empty string")
        if self._repository.doctrine_name_exists(doctrine_name):
            raise ValueError("doctrine_name already exists")
        doctrine_id = self._repository.get_next_doctrine_id()
        if self._repository.doctrine_id_exists(doctrine_id):
            raise ValueError(f"doctrine_id {doctrine_id} already exists")
        self._repository.create_doctrine(doctrine_id=doctrine_id, doctrine_name=doctrine_name)

        if not self._repository.doctrine_id_exists(doctrine_id):
            raise AdminWriteIntegrityError(
                f"create_doctrine read-back mismatch: doctrine_id={doctrine_id} "
                "not visible after apparent successful write"
            )

        self._cache_invalidator()
        logger.info(
            "doctrine_created character_id=%s character_name=%s write_target=%s "
            "doctrine_id=%s doctrine_name=%r",
            int(payload["character_id"]),
            payload.get("character_name", ""),
            self._repository.write_target,
            doctrine_id,
            doctrine_name,
        )
        return {"doctrine_id": doctrine_id, "doctrine_name": doctrine_name}

    def rename_doctrine(
        self,
        *,
        doctrine_id: int,
        doctrine_name: str,
        signed_identity: dict | None,
    ) -> dict:
        """Rename an existing doctrine by updating its raw doctrine_name."""
        payload = self._require_admin(signed_identity)
        doctrine_id = int(doctrine_id)
        doctrine_name = doctrine_name.strip()
        if not doctrine_name:
            raise ValueError("doctrine_name must be a non-empty string")
        existing_name = self._repository.get_doctrine_name(doctrine_id)
        if not existing_name:
            raise ValueError(f"No doctrine found for doctrine_id={doctrine_id}")
        if existing_name.strip().lower() != doctrine_name.lower():
            if self._repository.doctrine_name_exists(doctrine_name):
                raise ValueError("doctrine_name already exists")

        self._repository.rename_doctrine(doctrine_id=doctrine_id, doctrine_name=doctrine_name)

        if self._repository.get_doctrine_name(doctrine_id) != doctrine_name:
            raise AdminWriteIntegrityError(
                f"rename_doctrine read-back mismatch: doctrine_id={doctrine_id} "
                "did not show the requested doctrine_name after apparent successful write"
            )

        self._cache_invalidator()
        logger.info(
            "doctrine_renamed character_id=%s character_name=%s write_target=%s "
            "doctrine_id=%s old_doctrine_name=%r new_doctrine_name=%r",
            int(payload["character_id"]),
            payload.get("character_name", ""),
            self._repository.write_target,
            doctrine_id,
            existing_name,
            doctrine_name,
        )
        return {"doctrine_id": doctrine_id, "doctrine_name": doctrine_name}

    def save_doctrine_fit(
        self,
        *,
        eft_text: str,
        doctrine_id: int,
        fit_id: int | None,
        target: int,
        market_flag: MarketFlag,
        mode: SaveMode,
        signed_identity: dict | None,
    ) -> dict:
        """Add or update one fit within an existing doctrine."""
        payload = self._require_admin(signed_identity)
        doctrine_id = int(doctrine_id)
        target = int(target)
        if target <= 0:
            raise ValueError("target must be greater than zero")
        if market_flag not in ("primary", "deployment", "both"):
            raise ValueError("market_flag must be primary, deployment, or both")

        parsed_fit = parse_eft_fit(eft_text)

        if mode == "update":
            if fit_id is None:
                raise ValueError("fit_id is required when updating a doctrine fit")
            fit_id = int(fit_id)
            existing_fit = self._repository.get_doctrine_fit(doctrine_id, fit_id)
            if existing_fit is None:
                raise ValueError(f"No doctrine fit found for doctrine_id={doctrine_id}, fit_id={fit_id}")
            doctrine_name = existing_fit["doctrine_name"]
        elif mode == "add":
            fit_id = self._repository.get_next_doctrine_fit_id()
            if self._repository.doctrine_fit_id_exists(fit_id):
                raise ValueError(f"fit_id {fit_id} already exists")
            doctrine_name = self._repository.get_doctrine_name(doctrine_id)
            if not doctrine_name:
                raise ValueError(f"No doctrine found for doctrine_id={doctrine_id}")
        else:
            raise ValueError("mode must be add or update")

        self._repository.save_doctrine_fit(
            doctrine_id=doctrine_id,
            doctrine_name=doctrine_name,
            fit_id=fit_id,
            fit_name=parsed_fit.fit_name,
            ship_name=parsed_fit.ship_name,
            item_quantities=parsed_fit.item_quantities,
            target=target,
            market_flag=market_flag,
            mode=mode,
        )

        if self._repository.get_doctrine_fit(doctrine_id, fit_id) is None:
            raise AdminWriteIntegrityError(
                f"save_doctrine_fit read-back mismatch: doctrine_id={doctrine_id} "
                f"fit_id={fit_id} not visible after apparent successful write"
            )

        self._cache_invalidator()
        logger.info(
            "doctrine_fit_saved character_id=%s character_name=%s write_target=%s "
            "mode=%s doctrine_id=%s fit_id=%s ship_name=%r fit_name=%r target=%d "
            "market_flag=%s item_count=%d",
            int(payload["character_id"]),
            payload.get("character_name", ""),
            self._repository.write_target,
            mode,
            doctrine_id,
            fit_id,
            parsed_fit.ship_name,
            parsed_fit.fit_name,
            target,
            market_flag,
            len(parsed_fit.item_quantities),
        )
        return {
            "doctrine_id": doctrine_id,
            "fit_id": fit_id,
            "item_count": len(parsed_fit.item_quantities),
        }

    def delete_doctrine_fit(
        self,
        *,
        doctrine_id: int,
        fit_id: int,
        signed_identity: dict | None,
    ) -> dict:
        """Delete one existing doctrine fit."""
        payload = self._require_admin(signed_identity)
        doctrine_id = int(doctrine_id)
        fit_id = int(fit_id)
        existing_fit = self._repository.get_doctrine_fit(doctrine_id, fit_id)
        if existing_fit is None:
            raise ValueError(f"No doctrine fit found for doctrine_id={doctrine_id}, fit_id={fit_id}")
        self._repository.delete_doctrine_fit(doctrine_id=doctrine_id, fit_id=fit_id)

        if self._repository.get_doctrine_fit(doctrine_id, fit_id) is not None:
            raise AdminWriteIntegrityError(
                f"delete_doctrine_fit read-back mismatch: doctrine_id={doctrine_id} "
                f"fit_id={fit_id} still visible after apparent successful delete"
            )

        self._cache_invalidator()
        logger.info(
            "doctrine_fit_deleted character_id=%s character_name=%s write_target=%s "
            "doctrine_id=%s fit_id=%s doctrine_name=%r",
            int(payload["character_id"]),
            payload.get("character_name", ""),
            self._repository.write_target,
            doctrine_id,
            fit_id,
            existing_fit.get("doctrine_name", ""),
        )
        return {"doctrine_id": doctrine_id, "fit_id": fit_id}

    def _require_admin(self, signed_identity: dict | None) -> dict:
        payload = self._auth_service.verify_signed_admin_identity(signed_identity)
        if payload is None:
            raise PermissionError("Admin authentication required")
        return payload

    def _normalize_rows(self, watchlist_df: pd.DataFrame | Iterable[dict]) -> list[dict]:
        if isinstance(watchlist_df, pd.DataFrame):
            frame = watchlist_df.copy()
        else:
            frame = pd.DataFrame(list(watchlist_df))
        unknown_columns = [column for column in frame.columns if column not in WATCHLIST_COLUMNS]
        if unknown_columns:
            raise ValueError(f"Unexpected columns: {', '.join(sorted(unknown_columns))}")
        missing_columns = [column for column in WATCHLIST_COLUMNS if column not in frame.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        if frame.empty:
            raise ValueError("Refusing to replace watchlist with an empty watchlist")
        return frame[WATCHLIST_COLUMNS].to_dict(orient="records")

    def _validate_rows(self, rows: list[dict]) -> None:
        seen_type_ids: set[int] = set()
        text_fields = ("type_name", "group_name", "category_name")
        int_fields = ("type_id", "group_id", "category_id")
        for row in rows:
            normalized = {}
            for field in int_fields:
                try:
                    normalized[field] = int(row[field])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"{field} must be an integer") from exc
            type_id = normalized["type_id"]
            if type_id in seen_type_ids:
                raise ValueError(f"Duplicate type_id: {type_id}")
            seen_type_ids.add(type_id)
            for field in text_fields:
                value = str(row.get(field, "")).strip()
                if not value:
                    raise ValueError(f"{field} must be a non-empty string")
                row[field] = value
            row.update(normalized)


def get_admin_service() -> AdminService:
    """Return the admin service for the active market."""
    return AdminService(get_admin_repository(), get_eve_sso_service())
