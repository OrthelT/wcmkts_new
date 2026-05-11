"""Tests for admin page helpers."""

import pandas as pd

from pages.admin import summarize_watchlist_changes


def test_summarize_watchlist_changes_counts_add_update_remove():
    original = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
            {
                "type_id": 35,
                "group_id": 18,
                "type_name": "Pyerite",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
        ]
    )
    edited = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Raw Material",
            },
            {
                "type_id": 36,
                "group_id": 18,
                "type_name": "Mexallon",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
        ]
    )

    summary = summarize_watchlist_changes(original, edited)

    assert summary == {"added": 1, "changed": 1, "removed": 1}
