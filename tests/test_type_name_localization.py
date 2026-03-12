"""Tests for generalized type-name localization helpers."""

import pandas as pd
from unittest.mock import Mock


def test_apply_localized_names_overwrites_requested_column_and_keeps_english_backup():
    from services.type_name_localization import apply_localized_names

    df = pd.DataFrame(
        {
            "ship_id": [1, 2],
            "ship_name": ["Drake", "Ferox"],
        }
    )

    sde_repo = Mock()
    sde_repo.get_localized_names.return_value = {1: "ドレイク", 2: "フェロックス"}
    result = apply_localized_names(
        df,
        sde_repo,
        "ja",
        id_column="ship_id",
        name_column="ship_name",
    )

    assert result["ship_name"].tolist() == ["ドレイク", "フェロックス"]
    assert result["ship_name_en"].tolist() == ["Drake", "Ferox"]


def test_apply_localized_names_to_records_keeps_english_backup():
    from services.type_name_localization import apply_localized_names_to_records

    records = [
        {"type_id": 34, "module_name": "Tritanium"},
        {"type_id": 35, "module_name": "Pyerite"},
    ]

    sde_repo = Mock()
    sde_repo.get_localized_names.return_value = {34: "三钛合金", 35: "类晶体胶矿"}
    result = apply_localized_names_to_records(
        records,
        sde_repo,
        "zh",
        id_key="type_id",
        name_key="module_name",
    )

    assert result[0]["module_name"] == "三钛合金"
    assert result[0]["module_name_en"] == "Tritanium"
    assert result[1]["module_name"] == "类晶体胶矿"
    assert result[1]["module_name_en"] == "Pyerite"


def test_get_localized_name_falls_back_when_translation_missing():
    from services.type_name_localization import get_localized_name

    sde_repo = Mock()
    sde_repo.get_localized_names.return_value = {}
    result = get_localized_name(34, "Tritanium", sde_repo, "ko")

    assert result == "Tritanium"
