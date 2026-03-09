"""
Type Name Localization Helpers

Applies localized item names to dataframes using SDE-backed translations.
"""

from __future__ import annotations

import logging

import pandas as pd

from config import DatabaseConfig
from repositories.sde_repo import SDERepository


def apply_localized_type_names(
    df: pd.DataFrame,
    sde_db: DatabaseConfig,
    language_code: str,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Overlay localized type names onto a dataframe when translations exist."""
    if df.empty or language_code == "en":
        return df

    if "type_id" not in df.columns or "type_name" not in df.columns:
        return df

    type_ids = (
        pd.to_numeric(df["type_id"], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    if not type_ids:
        return df

    try:
        localized_names = SDERepository(sde_db).get_localized_type_names(type_ids, language_code)
    except Exception as exc:
        if logger is not None:
            logger.error("Failed to resolve localized type names: %s", exc)
        return df

    if not localized_names:
        return df

    result = df.copy()
    if "type_name_en" not in result.columns:
        result["type_name_en"] = result["type_name"]

    result["type_name"] = result["type_id"].map(
        lambda value: localized_names.get(int(value))
        if pd.notna(value) and int(value) in localized_names
        else None
    ).fillna(result["type_name"])

    return result
