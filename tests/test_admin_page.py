"""Tests for pure helpers in pages/admin.py."""

import pandas as pd
import pytest

from pages.admin import lookup_sde_row


@pytest.fixture
def sdetypes_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "typeID": 34,
                "typeName": "Tritanium",
                "groupID": 18,
                "groupName": "Mineral",
                "categoryID": 4,
                "categoryName": "Material",
            },
            {
                "typeID": 35,
                "typeName": "Pyerite",
                "groupID": 18,
                "groupName": "Mineral",
                "categoryID": 4,
                "categoryName": "Material",
            },
        ]
    )


def test_lookup_sde_row_by_type_id_returns_watchlist_shaped_dict(sdetypes_df):
    result = lookup_sde_row(sdetypes_df, type_id=34)

    assert result == {
        "type_id": 34,
        "group_id": 18,
        "type_name": "Tritanium",
        "group_name": "Mineral",
        "category_id": 4,
        "category_name": "Material",
    }


def test_lookup_sde_row_by_type_name_returns_watchlist_shaped_dict(sdetypes_df):
    result = lookup_sde_row(sdetypes_df, type_name="Pyerite")

    assert result == {
        "type_id": 35,
        "group_id": 18,
        "type_name": "Pyerite",
        "group_name": "Mineral",
        "category_id": 4,
        "category_name": "Material",
    }


def test_lookup_sde_row_returns_none_for_unknown_type_id(sdetypes_df):
    assert lookup_sde_row(sdetypes_df, type_id=99999999) is None


def test_lookup_sde_row_returns_none_for_unknown_type_name(sdetypes_df):
    assert lookup_sde_row(sdetypes_df, type_name="No Such Item") is None


def test_lookup_sde_row_requires_exactly_one_of_type_id_or_type_name(sdetypes_df):
    with pytest.raises(ValueError, match="exactly one of type_id or type_name"):
        lookup_sde_row(sdetypes_df, type_id=34, type_name="Tritanium")

    with pytest.raises(ValueError, match="exactly one of type_id or type_name"):
        lookup_sde_row(sdetypes_df)


def test_lookup_sde_row_is_case_sensitive_for_type_name(sdetypes_df):
    """Case-sensitive on purpose — matches the project no-wrong-data rule and
    mirrors AdminRepository._resolve_type_metadata behavior."""
    assert lookup_sde_row(sdetypes_df, type_name="tritanium") is None
