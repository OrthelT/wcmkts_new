"""Admin service for guarded watchlist and doctrine edits."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from repositories.admin_repo import WATCHLIST_COLUMNS, get_admin_repository
from services.eft_parser_service import parse_eft_fit
from services.eve_sso_service import get_eve_sso_service
from state.market_state import refresh_market_caches


class AdminService:
    """Validate and persist authenticated admin edits."""

    def __init__(self, repository, auth_service, *, cache_invalidator=refresh_market_caches):
        self._repository = repository
        self._auth_service = auth_service
        self._cache_invalidator = cache_invalidator

    def get_watchlist(self) -> pd.DataFrame:
        """Return the current watchlist."""
        return self._repository.get_watchlist()

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
        self._repository.replace_watchlist(rows)
        self._cache_invalidator()
        return {"row_count": len(rows), "character_id": int(payload["character_id"])}

    def save_doctrine_fit(
        self,
        *,
        eft_text: str,
        doctrine_id: int,
        fit_id: int | None,
        target: int,
        market_flag: str,
        mode: str,
        signed_identity: dict | None,
    ) -> dict:
        """Add or update one fit within an existing doctrine."""
        self._require_admin(signed_identity)
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
        self._cache_invalidator()
        return {
            "doctrine_id": doctrine_id,
            "fit_id": fit_id,
            "item_count": len(parsed_fit.item_quantities),
        }

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
