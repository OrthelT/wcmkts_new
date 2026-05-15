"""Tests for watchlist admin repository writes."""

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from sqlalchemy import create_engine, text

from repositories.admin_repo import (
    DOCTRINE_FIT_OPTION_COLUMNS,
    AdminRepository,
)


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


def _create_doctrine_admin_db(path: Path) -> None:
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
                CREATE TABLE doctrine_fits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctrine_name TEXT,
                    fit_name TEXT,
                    ship_type_id INTEGER,
                    doctrine_id INTEGER,
                    fit_id INTEGER,
                    ship_name TEXT,
                    target INTEGER,
                    market_flag TEXT,
                    friendly_name TEXT DEFAULT NULL
                )
                """
            )
        )
        conn.execute(text("CREATE TABLE doctrine_map (id BIGINT, doctrine_id BIGINT, fitting_id BIGINT)"))
        conn.execute(
            text(
                """
                CREATE TABLE lead_ships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctrine_name TEXT,
                    doctrine_id INTEGER,
                    lead_ship INTEGER,
                    fit_id INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE ship_targets (
                    fit_id INTEGER PRIMARY KEY,
                    fit_name TEXT NOT NULL,
                    ship_id INTEGER NOT NULL,
                    ship_name TEXT NOT NULL,
                    ship_target INTEGER NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE doctrines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fit_id INTEGER,
                    ship_id INTEGER,
                    ship_name TEXT,
                    hulls INTEGER,
                    type_id INTEGER,
                    type_name TEXT,
                    fit_qty INTEGER,
                    fits_on_mkt INTEGER,
                    total_stock INTEGER,
                    price FLOAT,
                    avg_vol INTEGER,
                    days FLOAT,
                    group_id INTEGER,
                    group_name TEXT,
                    category_id INTEGER,
                    category_name TEXT,
                    timestamp TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE marketstats (
                    type_id INTEGER PRIMARY KEY,
                    total_volume_remain INTEGER NOT NULL,
                    min_price FLOAT NOT NULL,
                    price FLOAT NOT NULL,
                    avg_price FLOAT NOT NULL,
                    avg_volume FLOAT NOT NULL,
                    group_id INTEGER NOT NULL,
                    type_name TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    category_name TEXT NOT NULL,
                    days_remaining FLOAT NOT NULL,
                    last_update DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE inv_info (
                    typeID INT,
                    typeName TEXT,
                    groupID INT,
                    volume REAL,
                    groupName TEXT,
                    categoryID INT,
                    categoryName TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO inv_info
                    (typeID, typeName, groupID, volume, groupName, categoryID, categoryName)
                VALUES
                    (1, 'Vedmak', 25, 10000, 'Cruiser', 6, 'Ship'),
                    (4, 'Caracal', 25, 10000, 'Cruiser', 6, 'Ship'),
                    (2, 'Damage Control II', 60, 5, 'Damage Control', 7, 'Module'),
                    (3, 'Entropic Radiation Sink II', 60, 5, 'Weapon Upgrade', 7, 'Module')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO marketstats
                    (
                        type_id, total_volume_remain, min_price, price, avg_price, avg_volume,
                        group_id, type_name, group_name, category_id, category_name,
                        days_remaining, last_update
                    )
                VALUES
                    (1, 12, 1.0, 100.0, 100.0, 2.0, 25, 'Vedmak', 'Cruiser', 6, 'Ship', 6.0, '2026-05-12'),
                    (4, 8, 1.0, 90.0, 90.0, 2.0, 25, 'Caracal', 'Cruiser', 6, 'Ship', 6.0, '2026-05-12'),
                    (2, 10, 1.0, 20.0, 20.0, 5.0, 60, 'Damage Control II', 'Damage Control', 7, 'Module', 2.0, '2026-05-12'),
                    (3, 9, 1.0, 30.0, 30.0, 3.0, 60, 'Entropic Radiation Sink II', 'Weapon Upgrade', 7, 'Module', 3.0, '2026-05-12')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO doctrine_fits
                    (doctrine_name, fit_name, ship_type_id, doctrine_id, fit_id, ship_name, target, market_flag)
                VALUES
                    ('Doctrine Alpha', 'Old Fit', 1, 10, 20, 'Vedmak', 25, 'primary')
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


def test_replace_watchlist_refuses_empty_rows(tmp_path):
    db_path = tmp_path / "watchlist.db"
    _create_watchlist_db(db_path)

    repo = AdminRepository.from_sqlite_path(db_path)

    try:
        repo.replace_watchlist([])
    except ValueError as exc:
        assert "empty watchlist" in str(exc)

    result = repo.get_watchlist()

    assert list(result["type_id"]) == [1]


def test_save_doctrine_fit_adds_new_fit_and_rebuilds_related_tables(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)

    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=99,
        fit_name="Test Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1, "Entropic Radiation Sink II": 2},
        target=50,
        market_flag="both",
        mode="add",
    )

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        fit = conn.execute(text("SELECT * FROM doctrine_fits WHERE fit_id = 99")).mappings().one()
        target = conn.execute(text("SELECT * FROM ship_targets WHERE fit_id = 99")).mappings().one()
        mapped = conn.execute(text("SELECT * FROM doctrine_map WHERE doctrine_id = 10 AND fitting_id = 99")).fetchone()
        lead_ship = conn.execute(text("SELECT * FROM lead_ships WHERE doctrine_id = 10")).mappings().one()
        doctrines = conn.execute(
            text("SELECT type_id, fit_qty, total_stock, fits_on_mkt FROM doctrines WHERE fit_id = 99 ORDER BY type_id")
        ).fetchall()
        watchlist_ids = conn.execute(text("SELECT type_id FROM watchlist ORDER BY type_id")).fetchall()

    assert fit["fit_name"] == "Test Vedmak"
    assert fit["ship_type_id"] == 1
    assert fit["target"] == 50
    assert fit["market_flag"] == "both"
    assert target["ship_target"] == 50
    assert mapped is not None
    assert lead_ship["lead_ship"] == 1
    assert lead_ship["fit_id"] == 99
    assert [(row.type_id, row.fit_qty) for row in doctrines] == [(1, 1), (2, 1), (3, 2)]
    assert [row.type_id for row in watchlist_ids] == [1, 2, 3]


def test_get_doctrine_fit_options_returns_current_fit_metadata(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)

    result = repo.get_doctrine_fit_options()

    assert list(result["doctrine_id"]) == [10]
    assert list(result["doctrine_name"]) == ["Doctrine Alpha"]
    assert list(result["fit_id"]) == [20]
    assert list(result["fit_name"]) == ["Old Fit"]
    assert list(result["ship_name"]) == ["Vedmak"]
    assert list(result["target"]) == [25]
    assert list(result["market_flag"]) == ["primary"]


def test_create_doctrine_records_empty_doctrine_without_linked_fit_rows(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)

    repo.create_doctrine(doctrine_id=11, doctrine_name="Doctrine Beta")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        doctrine = conn.execute(
            text("SELECT * FROM doctrine_fits WHERE doctrine_id = 11")
        ).mappings().one()
        targets = conn.execute(text("SELECT COUNT(*) FROM ship_targets WHERE fit_id IS NULL")).scalar_one()
        mapped = conn.execute(
            text("SELECT COUNT(*) FROM doctrine_map WHERE doctrine_id = 11")
        ).scalar_one()
        lead_ship = conn.execute(
            text("SELECT COUNT(*) FROM lead_ships WHERE doctrine_id = 11")
        ).scalar_one()
        doctrine_rows = conn.execute(
            text("SELECT COUNT(*) FROM doctrines WHERE fit_id IS NULL")
        ).scalar_one()

    assert doctrine["doctrine_name"] == "Doctrine Beta"
    assert doctrine["fit_id"] is None
    assert doctrine["fit_name"] is None
    assert doctrine["ship_type_id"] is None
    assert targets == 0
    assert mapped == 0
    assert lead_ship == 0
    assert doctrine_rows == 0


def test_create_doctrine_rejects_duplicate_doctrine_name_case_insensitive(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)

    try:
        repo.create_doctrine(doctrine_id=11, doctrine_name=" doctrine alpha ")
    except ValueError as exc:
        assert "doctrine_name already exists" in str(exc)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        doctrine_count = conn.execute(
            text("SELECT COUNT(*) FROM doctrine_fits WHERE doctrine_id = 11")
        ).scalar_one()

    assert doctrine_count == 0


def test_get_doctrine_fit_options_returns_schema_on_disk_io_error():
    engine = MagicMock()
    engine.connect.side_effect = ValueError("disk I/O error")
    repo = AdminRepository._from_engine(engine)

    result = repo.get_doctrine_fit_options()

    assert result.empty
    assert list(result.columns) == DOCTRINE_FIT_OPTION_COLUMNS


def test_get_next_doctrine_fit_id_uses_next_available_id(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)

    assert repo.get_next_doctrine_fit_id() == 21


def test_prepare_local_write_disposes_stale_connections():
    db = MagicMock()
    repo = AdminRepository(db, write_target="local")

    repo._prepare_local_write()

    db._dispose_local_connections.assert_called_once()


def test_default_write_engine_uses_remote_target():
    db = MagicMock()
    db.engine = object()
    db.remote_engine = object()
    repo = AdminRepository(db)

    assert repo._get_write_engine() is db.remote_engine


def test_remote_admin_reader_reads_remote_source():
    db = MagicMock()
    repo = AdminRepository(db, write_target="remote")
    repo._reader = MagicMock()
    repo._reader.read_df.return_value = pd.DataFrame(columns=["type_id"])

    repo.get_watchlist()

    _, kwargs = repo._reader.read_df.call_args
    assert kwargs["local"] is False


def test_get_doctrine_fit_eft_returns_current_fit_text(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)
    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=20,
        fit_name="Updated Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1, "Entropic Radiation Sink II": 2},
        target=40,
        market_flag="deployment",
        mode="update",
    )

    result = repo.get_doctrine_fit_eft(20)

    assert result == (
        "[Vedmak, Updated Vedmak]\n"
        "Damage Control II\n"
        "Entropic Radiation Sink II x2"
    )


def test_save_doctrine_fit_update_replaces_existing_fit_rows(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)

    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=20,
        fit_name="Updated Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1},
        target=40,
        market_flag="deployment",
        mode="update",
    )

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        fit = conn.execute(text("SELECT * FROM doctrine_fits WHERE fit_id = 20")).mappings().one()
        doctrines = conn.execute(
            text("SELECT type_id, fit_qty FROM doctrines WHERE fit_id = 20 ORDER BY type_id")
        ).fetchall()

    assert fit["fit_name"] == "Updated Vedmak"
    assert fit["target"] == 40
    assert fit["market_flag"] == "deployment"
    assert [(row.type_id, row.fit_qty) for row in doctrines] == [(1, 1), (2, 1)]


def test_save_doctrine_fit_add_removes_empty_doctrine_placeholder(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)
    repo.create_doctrine(doctrine_id=11, doctrine_name="Doctrine Beta")

    repo.save_doctrine_fit(
        doctrine_id=11,
        doctrine_name="Doctrine Beta",
        fit_id=99,
        fit_name="Beta Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1},
        target=30,
        market_flag="primary",
        mode="add",
    )

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        fit_rows = conn.execute(
            text("SELECT fit_id FROM doctrine_fits WHERE doctrine_id = 11 ORDER BY fit_id")
        ).fetchall()

    assert [row.fit_id for row in fit_rows] == [99]


def test_delete_doctrine_fit_removes_last_fit_and_keeps_empty_doctrine_placeholder(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)
    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=20,
        fit_name="Updated Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1},
        target=40,
        market_flag="primary",
        mode="update",
    )

    repo.delete_doctrine_fit(doctrine_id=10, fit_id=20)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        fit_rows = conn.execute(
            text("SELECT doctrine_name, fit_id FROM doctrine_fits WHERE doctrine_id = 10")
        ).fetchall()
        target_count = conn.execute(
            text("SELECT COUNT(*) FROM ship_targets WHERE fit_id = 20")
        ).scalar_one()
        map_count = conn.execute(
            text("SELECT COUNT(*) FROM doctrine_map WHERE doctrine_id = 10 AND fitting_id = 20")
        ).scalar_one()
        doctrine_count = conn.execute(
            text("SELECT COUNT(*) FROM doctrines WHERE fit_id = 20")
        ).scalar_one()
        lead_count = conn.execute(
            text("SELECT COUNT(*) FROM lead_ships WHERE doctrine_id = 10")
        ).scalar_one()

    assert [(row.doctrine_name, row.fit_id) for row in fit_rows] == [("Doctrine Alpha", None)]
    assert target_count == 0
    assert map_count == 0
    assert doctrine_count == 0
    assert lead_count == 0


def test_delete_doctrine_fit_promotes_remaining_fit_as_lead_ship(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)
    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=20,
        fit_name="Lead Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1},
        target=40,
        market_flag="primary",
        mode="update",
    )
    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=99,
        fit_name="Backup Vedmak",
        ship_name="Vedmak",
        item_quantities={"Entropic Radiation Sink II": 1},
        target=35,
        market_flag="primary",
        mode="add",
    )

    repo.delete_doctrine_fit(doctrine_id=10, fit_id=20)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        remaining_fits = conn.execute(
            text("SELECT fit_id FROM doctrine_fits WHERE doctrine_id = 10 ORDER BY fit_id")
        ).fetchall()
        lead_ship = conn.execute(
            text("SELECT lead_ship, fit_id FROM lead_ships WHERE doctrine_id = 10")
        ).mappings().one()

    assert [row.fit_id for row in remaining_fits] == [99]
    assert lead_ship["lead_ship"] == 1
    assert lead_ship["fit_id"] == 99


def test_update_doctrine_fit_refreshes_existing_lead_ship(tmp_path):
    db_path = tmp_path / "doctrine.db"
    _create_doctrine_admin_db(db_path)
    repo = AdminRepository.from_sqlite_path(db_path)
    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=20,
        fit_name="Lead Vedmak",
        ship_name="Vedmak",
        item_quantities={"Damage Control II": 1},
        target=40,
        market_flag="primary",
        mode="update",
    )

    repo.save_doctrine_fit(
        doctrine_id=10,
        doctrine_name="Doctrine Alpha",
        fit_id=20,
        fit_name="Lead Caracal",
        ship_name="Caracal",
        item_quantities={"Damage Control II": 1},
        target=40,
        market_flag="primary",
        mode="update",
    )

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        lead_ship = conn.execute(
            text("SELECT lead_ship, fit_id FROM lead_ships WHERE doctrine_id = 10")
        ).mappings().one()

    assert lead_ship["lead_ship"] == 4
    assert lead_ship["fit_id"] == 20
