"""Tests for multilingual SDE item resolution in the Pricer service."""

from unittest.mock import Mock

from sqlalchemy import create_engine, text


def _build_lookup_service():
    from services.pricer_service import SDELookupService

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE sdetypes ("
            " typeID INTEGER PRIMARY KEY,"
            " typeName TEXT,"
            " groupName TEXT,"
            " categoryName TEXT,"
            " volume REAL,"
            " repackagedVolume REAL)"
        ))
        conn.execute(text(
            "CREATE TABLE localizations ("
            " type_id INTEGER,"
            " language TEXT,"
            " type_name TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO sdetypes VALUES "
            " (18, 'Plagioclase', 'Ore', 'Asteroid', 0.35, NULL),"
            " (34, 'Tritanium', 'Mineral', 'Material', 0.01, NULL),"
            " (587, 'Rifter', 'Frigate', 'Ship', 27289.0, 2500.0)"
        ))
        conn.execute(text(
            "INSERT INTO localizations VALUES "
            " (18, 'zh', '斜长岩'),"
            " (18, 'ko', '사장석'),"
            " (34, 'zh', '三钛合金')"
        ))

    mock_db = Mock()
    type(mock_db).engine = engine
    return SDELookupService(mock_db)


def test_resolve_item_matches_exact_localized_name():
    service = _build_lookup_service()

    result = service.resolve_item("斜长岩")

    assert result is not None
    assert result["type_id"] == 18
    assert result["type_name"] == "Plagioclase"


def test_resolve_item_matches_localized_prefix():
    service = _build_lookup_service()

    result = service.resolve_item("三钛")

    assert result is not None
    assert result["type_id"] == 34
    assert result["type_name"] == "Tritanium"


def test_resolve_item_prefers_repackaged_volume():
    service = _build_lookup_service()

    assert service.resolve_item("Rifter")["volume"] == 2500.0
    assert service.resolve_item("Tritanium")["volume"] == 0.01
