"""Build-cost service backed by stored market-database rows."""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from logging_config import setup_logging

logger = setup_logging(__name__, log_file="build_cost_service.log")

BUILDER_COST_COLUMNS = [
    "type_id",
    "type_name",
    "group_id",
    "group_name",
    "category_id",
    "category_name",
    "total_cost_per_unit",
    "time_per_unit",
    "me",
    "runs",
    "fetched_at",
]


def _optional_float(value) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> Optional[int]:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class BuildCostSnapshot:
    """Stored build-cost data for a single item and requested quantity."""

    type_id: int
    type_name: str
    group_id: Optional[int]
    group_name: Optional[str]
    category_id: Optional[int]
    category_name: Optional[str]
    quantity: int
    total_cost_per_unit: float
    total_cost: float
    time_per_unit: Optional[float]
    total_time: Optional[float]
    me: Optional[int]
    runs: Optional[int]
    fetched_at: Optional[str]


class BuildCostService:
    """Service for browsing stored builder costs."""

    def __init__(self, repo):
        self._repo = repo

    def get_available_costs(self) -> pd.DataFrame:
        """Return stored builder-cost rows sorted for sidebar filtering."""
        if not hasattr(self._repo, "get_builder_cost_catalog"):
            return pd.DataFrame(columns=BUILDER_COST_COLUMNS)

        df = self._repo.get_builder_cost_catalog()
        if df.empty:
            return pd.DataFrame(columns=BUILDER_COST_COLUMNS)

        available_columns = [column for column in BUILDER_COST_COLUMNS if column in df.columns]
        sort_columns = [
            column for column in ("category_name", "group_name", "type_name") if column in df.columns
        ]
        result = df.loc[:, available_columns]
        if sort_columns:
            result = result.sort_values(by=sort_columns, kind="stable")
        return result.reset_index(drop=True)

    def get_cost_snapshot(self, type_id: int, quantity: int = 1) -> Optional[BuildCostSnapshot]:
        """Build a display-friendly snapshot from a stored builder-cost row."""
        if not hasattr(self._repo, "get_builder_cost_by_type"):
            return None

        df = self._repo.get_builder_cost_by_type(type_id)
        if df.empty:
            return None

        row = df.iloc[0]
        cost_per_unit = _optional_float(row.get("total_cost_per_unit"))
        if cost_per_unit is None:
            return None

        safe_quantity = max(int(quantity), 1)
        time_per_unit = _optional_float(row.get("time_per_unit"))

        return BuildCostSnapshot(
            type_id=int(row.get("type_id", type_id)),
            type_name=str(row.get("type_name") or type_id),
            group_id=_optional_int(row.get("group_id")),
            group_name=row.get("group_name"),
            category_id=_optional_int(row.get("category_id")),
            category_name=row.get("category_name"),
            quantity=safe_quantity,
            total_cost_per_unit=cost_per_unit,
            total_cost=cost_per_unit * safe_quantity,
            time_per_unit=time_per_unit,
            total_time=(time_per_unit * safe_quantity) if time_per_unit is not None else None,
            me=_optional_int(row.get("me")),
            runs=_optional_int(row.get("runs")),
            fetched_at=str(row.get("fetched_at")) if row.get("fetched_at") is not None else None,
        )

def get_build_cost_service() -> BuildCostService:
    """Get or create the build-cost service for the active market."""

    def _create() -> BuildCostService:
        from repositories.market_repo import get_market_repository

        return BuildCostService(get_market_repository())

    try:
        from state import get_service
        from state.market_state import get_active_market_key

        return get_service(f"build_cost_service_{get_active_market_key()}", _create)
    except ImportError:
        return _create()
