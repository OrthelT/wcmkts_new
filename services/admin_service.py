"""Admin service for guarded watchlist edits."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from repositories.admin_repo import WATCHLIST_COLUMNS, get_admin_repository
from services.eve_sso_service import get_eve_sso_service
from state.market_state import refresh_market_caches


class AdminService:
    """Validate and persist watchlist edits for authenticated admins."""

    def __init__(self, repository, auth_service, *, cache_invalidator=refresh_market_caches):
        self._repository = repository
        self._auth_service = auth_service
        self._cache_invalidator = cache_invalidator

    def get_watchlist(self) -> pd.DataFrame:
        """Return the current watchlist."""
        return self._repository.get_watchlist()

    def save_watchlist(self, watchlist_df: pd.DataFrame, *, signed_identity: dict | None) -> dict:
        """Validate and replace the watchlist table for the active market."""
        payload = self._auth_service.verify_signed_admin_identity(signed_identity)
        if payload is None:
            raise PermissionError("Admin authentication required")

        rows = self._normalize_rows(watchlist_df)
        self._validate_rows(rows)
        self._repository.replace_watchlist(rows)
        self._cache_invalidator()
        return {"row_count": len(rows), "character_id": int(payload["character_id"])}

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
