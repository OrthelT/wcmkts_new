"""Data adapter for the NiceGUI proof-of-concept.

The whole point of the POC is to show that the *existing* service/repository
layer ports to a non-Streamlit framework untouched. So we try the real
DoctrineService first. If no local DB has been synced (the common case on a
fresh checkout with no Turso secrets), we fall back to a representative sample
frame and flag it loudly — per the project's data-integrity rule we NEVER
present sample data as if it were real.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Put the repo root on the path so we can import the real services unchanged.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("poc.data")

# Columns mirror the doctrine dashboard view (see ui/column_definitions.py).
_DOCTRINE_COLUMNS = [
    "ship_name",
    "fit_id",
    "fits_on_mkt",
    "ship_target",
    "hulls",
    "price",
    "daily_avg",
]


@dataclass
class DoctrineTable:
    """A doctrine fits frame plus provenance so the UI can be honest about it."""

    df: pd.DataFrame
    is_sample: bool
    note: str


def _compute_pct_target(df: pd.DataFrame) -> pd.DataFrame:
    """Add the '% target' column the dashboard task asked for."""
    df = df.copy()
    target = df["ship_target"].replace(0, pd.NA)
    df["pct_target"] = (df["fits_on_mkt"] / target * 100).round(0).fillna(0).astype(int)
    return df


def _sample_frame() -> pd.DataFrame:
    rows = [
        ("Ferox Navy Issue", 101, 18, 50, 22, 78_000_000, 3.1),
        ("Hurricane", 102, 47, 40, 51, 62_000_000, 5.4),
        ("Eagle", 103, 6, 30, 8, 121_000_000, 1.2),
        ("Guardian", 104, 12, 20, 14, 195_000_000, 0.8),
        ("Scimitar", 105, 31, 25, 33, 188_000_000, 1.6),
        ("Huginn", 106, 2, 12, 3, 240_000_000, 0.4),
        ("Cyclone", 107, 58, 35, 60, 55_000_000, 6.2),
        ("Devoter", 108, 0, 10, 1, 310_000_000, 0.2),
    ]
    return pd.DataFrame(rows, columns=_DOCTRINE_COLUMNS)


def get_doctrine_table() -> DoctrineTable:
    """Return doctrine fit data, preferring the real service layer.

    Demonstrates that pages/ is the *only* layer we replace: services/,
    repositories/, domain/ all come along for free.
    """
    try:
        from services.doctrine_service import DoctrineService

        service = DoctrineService.create_default()
        df = service.repository.get_all_fits()
        if df is None or df.empty:
            raise RuntimeError("doctrine repository returned no rows")
        df = _compute_pct_target(df)
        return DoctrineTable(df=df, is_sample=False, note="Live data from your synced DB.")
    except Exception as exc:  # noqa: BLE001 - POC: any failure → honest fallback
        logger.warning("Real service layer unavailable (%s); using sample data.", exc)
        df = _compute_pct_target(_sample_frame())
        return DoctrineTable(
            df=df,
            is_sample=True,
            note=(
                "SAMPLE DATA — no local DB synced (no Turso secrets). This is the "
                "same code path that would render your live doctrine table once a "
                "DB is present; the numbers below are fabricated for layout only."
            ),
        )
