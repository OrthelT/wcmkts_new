"""Utilities for seeding local demo databases for offline testing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from build_cost_models import Base as BuildCostBase, IndustryIndex, Rig, Structure
from models import (
    Base as MarketBase,
    DoctrineFit,
    Doctrines,
    LeadShips,
    MarketHistory,
    MarketOrders,
    MarketStats,
    ShipTargets,
    UpdateLog,
    Watchlist,
)
from sdemodels import (
    Base as SdeBase,
    InvCategories,
    InvGroups,
    InvMetaGroups,
    InvMetaTypes,
    InvTypes,
    SdeTypes,
)
from settings_service import _load_settings

DEMO_SHIP_TYPE_ID = 16227

DEMO_ITEMS = [
    {
        "type_id": 31408,
        "type_name": "Medium Semiconductor Memory Cell I",
        "group_id": 9001,
        "group_name": "Rig",
        "category_id": 7,
        "category_name": "Module",
        "price": 1_579_394.7030532788,
        "days_remaining": 0.0,
        "avg_volume": 16.2,
        "total_volume_remain": 0,
        "volume_m3": 5.0,
    },
    {
        "type_id": 19927,
        "type_name": "Hypnos Scoped Magnetometric ECM",
        "group_id": 9002,
        "group_name": "ECM",
        "category_id": 7,
        "category_name": "Module",
        "price": 9_566.440674157304,
        "days_remaining": 0.0,
        "avg_volume": 12.7,
        "total_volume_remain": 0,
        "volume_m3": 5.0,
    },
    {
        "type_id": 5849,
        "type_name": "Extruded Compact Heat Sink",
        "group_id": 9003,
        "group_name": "Heat Sink",
        "category_id": 7,
        "category_name": "Module",
        "price": 107_500.0,
        "days_remaining": 0.1,
        "avg_volume": 27.5,
        "total_volume_remain": 4,
        "volume_m3": 5.0,
    },
    {
        "type_id": 5365,
        "type_name": "Cetus Scoped Burst Jammer",
        "group_id": 9004,
        "group_name": "Burst Jammer",
        "category_id": 7,
        "category_name": "Module",
        "price": 99_980.0,
        "days_remaining": 0.2,
        "avg_volume": 4.7,
        "total_volume_remain": 1,
        "volume_m3": 5.0,
    },
    {
        "type_id": 6160,
        "type_name": "F-90 Compact Sensor Booster",
        "group_id": 9005,
        "group_name": "Sensor Booster",
        "category_id": 7,
        "category_name": "Module",
        "price": 19_791.0,
        "days_remaining": 0.5,
        "avg_volume": 39.4,
        "total_volume_remain": 21,
        "volume_m3": 5.0,
    },
    {
        "type_id": 31274,
        "type_name": "Small Ionic Field Projector I",
        "group_id": 9001,
        "group_name": "Rig",
        "category_id": 7,
        "category_name": "Module",
        "price": 190_500.0,
        "days_remaining": 0.7,
        "avg_volume": 16.2,
        "total_volume_remain": 12,
        "volume_m3": 5.0,
    },
    {
        "type_id": 19325,
        "type_name": "Coreli A-Type 5MN Microwarpdrive",
        "group_id": 9006,
        "group_name": "Microwarpdrive",
        "category_id": 7,
        "category_name": "Module",
        "price": 43_290_000.0,
        "days_remaining": 0.9,
        "avg_volume": 3.2,
        "total_volume_remain": 3,
        "volume_m3": 5.0,
    },
    {
        "type_id": 41218,
        "type_name": "Republic Fleet Large Cap Battery",
        "group_id": 9007,
        "group_name": "Cap Battery",
        "category_id": 7,
        "category_name": "Module",
        "price": 30_943_000.0,
        "days_remaining": 1.4,
        "avg_volume": 42.9,
        "total_volume_remain": 62,
        "volume_m3": 10.0,
    },
    {
        "type_id": 19015,
        "type_name": "Coreli A-Type Small Armor Repairer",
        "group_id": 9008,
        "group_name": "Armor Repairer",
        "category_id": 7,
        "category_name": "Module",
        "price": 33_570_000.0,
        "days_remaining": 1.4,
        "avg_volume": 2.2,
        "total_volume_remain": 3,
        "volume_m3": 5.0,
    },
    {
        "type_id": 4027,
        "type_name": "Fleeting Compact Stasis Webifier",
        "group_id": 9009,
        "group_name": "Stasis Webifier",
        "category_id": 7,
        "category_name": "Module",
        "price": 61_325.5,
        "days_remaining": 1.7,
        "avg_volume": 61.5,
        "total_volume_remain": 107,
        "volume_m3": 5.0,
    },
    {
        "type_id": 4871,
        "type_name": "Large Compact Pb-Acid Cap Battery",
        "group_id": 9007,
        "group_name": "Cap Battery",
        "category_id": 7,
        "category_name": "Module",
        "price": 85_000.0,
        "days_remaining": 1.7,
        "avg_volume": 117.8,
        "total_volume_remain": 204,
        "volume_m3": 10.0,
    },
]


def _remove_existing(path: Path, force: bool) -> None:
    if not path.exists():
        return
    if not force:
        raise FileExistsError(
            f"{path} already exists. Re-run with --force to overwrite demo data."
        )
    for suffix in ("", "-shm", "-wal", "-info"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def _seed_market_db(path: Path, market_name: str, price_multiplier: float) -> None:
    engine = create_engine(f"sqlite:///{path}")
    MarketBase.metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    history_start = now - timedelta(days=34)
    base_items = []
    for item in DEMO_ITEMS:
        seeded_item = item.copy()
        seeded_item["price"] = seeded_item["price"] * price_multiplier
        base_items.append(seeded_item)

    with Session(engine) as session:
        for item in base_items:
            session.add(
                MarketStats(
                    type_id=item["type_id"],
                    total_volume_remain=item["total_volume_remain"],
                    min_price=item["price"] * 0.98,
                    price=item["price"],
                    avg_price=item["price"] * 1.01,
                    avg_volume=item["avg_volume"],
                    group_id=item["group_id"],
                    type_name=item["type_name"],
                    group_name=item["group_name"],
                    category_id=item["category_id"],
                    category_name=item["category_name"],
                    days_remaining=item["days_remaining"],
                    last_update=now,
                )
            )

        order_id = 1
        for item in base_items:
            order_specs = []
            if item["total_volume_remain"] > 0:
                primary_sell = max(1, int(item["total_volume_remain"] * 0.6))
                secondary_sell = max(0, item["total_volume_remain"] - primary_sell)
                order_specs.append((False, 1.00, primary_sell))
                if secondary_sell > 0:
                    order_specs.append((False, 1.03, secondary_sell))
            order_specs.append(
                (
                    True,
                    0.94,
                    max(1, int(max(item["avg_volume"], item["total_volume_remain"]) * 0.2)),
                )
            )

            for is_buy_order, price_factor, volume in order_specs:
                session.add(
                    MarketOrders(
                        order_id=order_id,
                        is_buy_order=is_buy_order,
                        type_id=item["type_id"],
                        type_name=item["type_name"],
                        duration=90,
                        issued=now - timedelta(hours=order_id),
                        price=item["price"] * price_factor,
                        volume_remain=volume,
                    )
                )
                order_id += 1

        history_id = 1
        for item in base_items:
            for day in range(35):
                date = history_start + timedelta(days=day)
                daily_price = item["price"] * (0.98 + (day % 5) * 0.01)
                daily_volume = max(1, int(item["avg_volume"] * (0.85 + (day % 7) * 0.04)))
                session.add(
                    MarketHistory(
                        id=history_id,
                        date=date,
                        type_name=item["type_name"],
                        type_id=str(item["type_id"]),
                        average=daily_price,
                        volume=daily_volume,
                        highest=daily_price * 1.03,
                        lowest=daily_price * 0.97,
                        order_count=12,
                        timestamp=date,
                    )
                )
                history_id += 1

        session.add(
            DoctrineFit(
                doctrine_name="Sample Doctrine",
                fit_name=f"{market_name} Ferox Fleet",
                ship_type_id=DEMO_SHIP_TYPE_ID,
                doctrine_id=1,
                fit_id=1,
                ship_name="Ferox",
                target=20,
                market_flag="primary",
            )
        )
        session.add(
            ShipTargets(
                fit_id=1,
                fit_name=f"{market_name} Ferox Fleet",
                ship_id=DEMO_SHIP_TYPE_ID,
                ship_name="Ferox",
                ship_target=20,
                created_at=now,
            )
        )
        session.add(
            LeadShips(
                doctrine_name="Sample Doctrine",
                doctrine_id=1,
                lead_ship=DEMO_SHIP_TYPE_ID,
                fit_id=1,
            )
        )
        for item in base_items[:3]:
            session.add(
                Doctrines(
                    fit_id=1,
                    ship_id=DEMO_SHIP_TYPE_ID,
                    ship_name="Ferox",
                    hulls=14,
                    type_id=item["type_id"],
                    type_name=item["type_name"],
                    fit_qty=1,
                    fits_on_mkt=14.0,
                    total_stock=item["total_volume_remain"],
                    price=item["price"],
                    avg_vol=item["avg_volume"],
                    days=item["days_remaining"],
                    group_id=item["group_id"],
                    group_name=item["group_name"],
                    category_id=item["category_id"],
                    category_name=item["category_name"],
                    timestamp=now,
                )
            )
        for item in base_items:
            session.add(
                Watchlist(
                    type_id=item["type_id"],
                    group_id=item["group_id"],
                    type_name=item["type_name"],
                    group_name=item["group_name"],
                    category_id=item["category_id"],
                    category_name=item["category_name"],
                )
            )
        for table_name in ("marketstats", "marketorders", "market_history"):
            session.add(UpdateLog(table_name=table_name, timestamp=now))

        session.commit()


def _seed_sde_db(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    SdeBase.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS industryActivityProducts (
                    productTypeID INTEGER,
                    activityID INTEGER
                )
                """
            )
        )

    with Session(engine) as session:
        categories = [
            InvCategories(categoryID=6, categoryName="Ship", iconID=0, published=True),
            InvCategories(categoryID=7, categoryName="Module", iconID=0, published=True),
        ]
        groups = [
            InvGroups(groupID=419, categoryID=6, groupName="Battlecruiser", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=False, published=True),
            InvGroups(groupID=9001, categoryID=7, groupName="Rig", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9002, categoryID=7, groupName="ECM", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9003, categoryID=7, groupName="Heat Sink", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9004, categoryID=7, groupName="Burst Jammer", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9005, categoryID=7, groupName="Sensor Booster", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9006, categoryID=7, groupName="Microwarpdrive", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9007, categoryID=7, groupName="Cap Battery", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9008, categoryID=7, groupName="Armor Repairer", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
            InvGroups(groupID=9009, categoryID=7, groupName="Stasis Webifier", iconID=0, useBasePrice=False, anchored=False, anchorable=False, fittableNonSingleton=True, published=True),
        ]
        meta_groups = [
            InvMetaGroups(metaGroupID=2, metaGroupName="Tech II"),
        ]
        items = [
            {
                "typeID": DEMO_SHIP_TYPE_ID,
                "typeName": "Ferox",
                "groupID": 419,
                "groupName": "Battlecruiser",
                "categoryID": 6,
                "categoryName": "Ship",
                "volume": 15000.0,
                "metaGroupID": None,
                "metaGroupName": None,
            }
        ]
        for item in DEMO_ITEMS:
            items.append(
                {
                    "typeID": item["type_id"],
                    "typeName": item["type_name"],
                    "groupID": item["group_id"],
                    "groupName": item["group_name"],
                    "categoryID": item["category_id"],
                    "categoryName": item["category_name"],
                    "volume": item["volume_m3"],
                    "metaGroupID": 2 if "II" in item["type_name"] else None,
                    "metaGroupName": "Tech II" if "II" in item["type_name"] else None,
                }
            )

        for category in categories:
            session.add(category)
        for group in groups:
            session.add(group)
        for meta_group in meta_groups:
            session.add(meta_group)

        for item in items:
            session.add(
                InvTypes(
                    typeID=item["typeID"],
                    groupID=item["groupID"],
                    typeName=item["typeName"],
                    mass=0.0,
                    volume=item["volume"],
                    capacity=0.0,
                    portionSize=1,
                    raceID=0,
                    basePrice=0.0,
                    published=True,
                    marketGroupID=0,
                    iconID=0,
                    soundID=0,
                    graphicID=0,
                )
            )
            session.add(
                SdeTypes(
                    typeID=item["typeID"],
                    typeName=item["typeName"],
                    groupID=item["groupID"],
                    groupName=item["groupName"],
                    categoryID=item["categoryID"],
                    categoryName=item["categoryName"],
                    volume=item["volume"],
                    metaGroupID=item["metaGroupID"],
                    metaGroupName=item["metaGroupName"],
                )
            )
            if item["metaGroupID"] is not None:
                session.add(
                    InvMetaTypes(
                        typeID=item["typeID"],
                        metaGroupID=item["metaGroupID"],
                    )
                )

        session.commit()

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO industryActivityProducts (productTypeID, activityID)
                VALUES
                    (1001, 1),
                    (1002, 1),
                    (1003, 1)
                """
            )
        )


def _seed_build_cost_db(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    BuildCostBase.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Rig(
                type_id=9001,
                type_name="Standup M-Set Ship Manufacturing Material Efficiency I",
                icon_id=0,
            )
        )
        session.add(
            Structure(
                system="4-HWWF",
                structure="Sample Sotiyo",
                system_id=30000240,
                structure_id=1035466617946,
                rig_1="Standup M-Set Ship Manufacturing Material Efficiency I",
                rig_2=None,
                rig_3=None,
                structure_type="Sotiyo",
                structure_type_id=35827,
                tax=0.03,
                region="The Forge",
                region_id=10000002,
            )
        )
        session.add(
            Structure(
                system="B-9C24",
                structure="Sample Azbel",
                system_id=30002029,
                structure_id=1046831245129,
                rig_1="Standup M-Set Ship Manufacturing Material Efficiency I",
                rig_2=None,
                rig_3=None,
                structure_type="Azbel",
                structure_type_id=35826,
                tax=0.04,
                region="Lonetrek",
                region_id=10000016,
            )
        )
        session.add(
            IndustryIndex(
                solar_system_id=30000240,
                manufacturing=0.045,
                researching_time_efficiency=0.0,
                researching_material_efficiency=0.0,
                copying=0.0,
                invention=0.0,
                reaction=0.0,
            )
        )
        session.add(
            IndustryIndex(
                solar_system_id=30002029,
                manufacturing=0.052,
                researching_time_efficiency=0.0,
                researching_material_efficiency=0.0,
                copying=0.0,
                invention=0.0,
                reaction=0.0,
            )
        )
        session.commit()


def seed_demo_data(force: bool = False) -> list[Path]:
    """Create local demo databases for browser testing without Turso."""
    settings = _load_settings()
    db_paths = settings["db_paths"]

    market_aliases = [
        settings["markets"]["primary"]["database_alias"],
        settings["markets"]["deployment"]["database_alias"],
    ]

    target_paths = [
        Path(db_paths[market_aliases[0]]),
        Path(db_paths[market_aliases[1]]),
        Path(db_paths["sde"]),
        Path(db_paths["build_cost"]),
    ]

    for path in target_paths:
        _remove_existing(path, force)

    _seed_market_db(Path(db_paths[market_aliases[0]]), "4-HWWF Keepstar", 1.0)
    _seed_market_db(Path(db_paths[market_aliases[1]]), "B-9C24 Keepstar", 1.08)
    _seed_sde_db(Path(db_paths["sde"]))
    _seed_build_cost_db(Path(db_paths["build_cost"]))

    return target_paths
