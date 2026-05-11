"""Tests for watchlist admin repository writes."""

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from repositories.admin_repo import AdminRepository


def _create_watchlist_db(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE watchlist (
                    type_id INTEGER PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    type_name TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    category_name TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO watchlist
                    (type_id, group_id, type_name, group_name, category_id, category_name)
                VALUES
                    (1, 10, 'Old Item', 'Old Group', 20, 'Old Category')
                """
            )
        )


def test_replace_watchlist_replaces_existing_rows(tmp_path):
    db_path = tmp_path / "watchlist.db"
    _create_watchlist_db(db_path)

    repo = AdminRepository.from_sqlite_path(db_path)
    rows = [
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

    repo.replace_watchlist(rows)
    result = repo.get_watchlist()

    assert list(result["type_id"]) == [34, 35]
    assert list(result["type_name"]) == ["Tritanium", "Pyerite"]


def test_replace_watchlist_is_transactional(tmp_path):
    db_path = tmp_path / "watchlist.db"
    _create_watchlist_db(db_path)

    repo = AdminRepository.from_sqlite_path(db_path)
    invalid_rows = [
        {
            "type_id": 34,
            "group_id": 18,
            "type_name": "Tritanium",
            "group_name": "Mineral",
            "category_id": 4,
            "category_name": "Material",
        },
        {
            "type_id": 34,
            "group_id": 18,
            "type_name": "Duplicate Tritanium",
            "group_name": "Mineral",
            "category_id": 4,
            "category_name": "Material",
        },
    ]

    try:
        repo.replace_watchlist(invalid_rows)
    except Exception:
        pass

    result = repo.get_watchlist()

    assert result.equals(
        pd.DataFrame(
            [
                {
                    "type_id": 1,
                    "group_id": 10,
                    "type_name": "Old Item",
                    "group_name": "Old Group",
                    "category_id": 20,
                    "category_name": "Old Category",
                }
            ]
        )
    )
