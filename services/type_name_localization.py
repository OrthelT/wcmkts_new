"""
Type Name Localization Helpers

Applies localized item names to dataframes using SDE-backed translations.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from repositories.sde_repo import SDERepository


def get_localized_name_map(
    type_ids: list[int],
    sde_repo: SDERepository,
    language_code: str,
    logger: logging.Logger | None = None,
) -> dict[int, str]:
    """Return localized names keyed by type ID."""
    if language_code == "en":
        return {}

    if not type_ids:
        return {}

    try:
        return sde_repo.get_localized_names(type_ids, language_code)
    except Exception as exc:
        if logger is not None:
            logger.error("Failed to resolve localized type names: %s", exc)
        return {}


def get_localized_name(
    type_id: int | None,
    fallback_name: str,
    sde_repo: SDERepository,
    language_code: str,
    logger: logging.Logger | None = None,
) -> str:
    """Return a localized display name for a single type ID."""
    if type_id is None or language_code == "en":
        return fallback_name

    localized_names = get_localized_name_map([int(type_id)], sde_repo, language_code, logger)
    return localized_names.get(int(type_id), fallback_name)


def apply_localized_names(
    df: pd.DataFrame,
    sde_repo: SDERepository,
    language_code: str,
    id_column: str,
    name_column: str,
    logger: logging.Logger | None = None,
    english_name_column: str | None = None,
) -> pd.DataFrame:
    """Overlay localized names onto any dataframe id/name column pair."""
    if df.empty or language_code == "en":
        return df

    if id_column not in df.columns or name_column not in df.columns:
        return df

    type_ids = (
        pd.to_numeric(df[id_column], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    localized_names = get_localized_name_map(type_ids, sde_repo, language_code, logger)

    if not localized_names:
        return df

    result = df.copy()
    if english_name_column is None:
        english_name_column = f"{name_column}_en"

    if english_name_column not in result.columns:
        result[english_name_column] = result[name_column]

    result[name_column] = result[id_column].map(
        lambda value: localized_names.get(int(value))
        if pd.notna(value) and int(value) in localized_names
        else None
    ).fillna(result[name_column])

    return result


def apply_localized_names_to_records(
    records: list[dict[str, Any]],
    sde_repo: SDERepository,
    language_code: str,
    id_key: str,
    name_key: str,
    logger: logging.Logger | None = None,
    english_name_key: str | None = None,
) -> list[dict[str, Any]]:
    """Overlay localized names onto a list of dictionaries."""
    if not records or language_code == "en":
        return records

    type_ids = []
    for record in records:
        value = record.get(id_key)
        if isinstance(value, int):
            type_ids.append(value)
        elif value is not None and str(value).isdigit():
            type_ids.append(int(value))

    localized_names = get_localized_name_map(type_ids, sde_repo, language_code, logger)
    if not localized_names:
        return records

    if english_name_key is None:
        english_name_key = f"{name_key}_en"

    localized_records: list[dict[str, Any]] = []
    for record in records:
        localized_record = dict(record)
        type_id = localized_record.get(id_key)
        if english_name_key not in localized_record:
            localized_record[english_name_key] = localized_record.get(name_key)
        if type_id is not None:
            try:
                localized_record[name_key] = localized_names.get(
                    int(type_id), localized_record.get(name_key)
                )
            except (TypeError, ValueError):
                pass
        localized_records.append(localized_record)

    return localized_records


def apply_localized_type_names(
    df: pd.DataFrame,
    sde_repo: SDERepository,
    language_code: str,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Overlay localized type names onto a dataframe when translations exist."""
    return apply_localized_names(
        df=df,
        sde_repo=sde_repo,
        language_code=language_code,
        id_column="type_id",
        name_column="type_name",
        logger=logger,
        english_name_column="type_name_en",
    )
