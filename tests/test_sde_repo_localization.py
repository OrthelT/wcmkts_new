"""
Tests for SDERepository localization methods.

Tests the localization _impl functions with mocked engines and an in-memory
SQLite database to verify the COALESCE/JOIN fallback logic.
"""

import pytest
from unittest.mock import Mock

from sqlalchemy import create_engine, text


def _mock_engine():
    """Create a mock engine with context-manager connect()."""
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine = Mock()
    mock_engine.connect.return_value = mock_conn
    return mock_engine, mock_conn


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine with a localizations table and test data.

    Seed data:
    - type_id 18 (Plagioclase): en + zh rows (fully localized)
    - type_id 91108 (Retriever SKIN): en only (no zh)
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE localizations ("
            "  type_id INTEGER, language TEXT, type_name TEXT,"
            "  PRIMARY KEY (type_id, language))"
        ))
        conn.execute(text(
            "INSERT INTO localizations VALUES"
            "  (18, 'en', 'Plagioclase'),"
            "  (18, 'zh', '斜长岩'),"
            "  (91108, 'en', 'Retriever Refined Resourcer SKIN')"
        ))
        conn.commit()
    return engine


class TestGetLocalizedName:
    def test_returns_name_when_found(self):
        from repositories.sde_repo import _get_localized_name_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchone.return_value = ("斜长石",)
        conn.execute.return_value = mock_result

        result = _get_localized_name_impl(engine, 18, "zh")
        assert result == "斜长石"

    def test_returns_none_when_not_found(self):
        from repositories.sde_repo import _get_localized_name_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        conn.execute.return_value = mock_result

        result = _get_localized_name_impl(engine, 99999999, "zh")
        assert result is None

    def test_falls_back_to_english(self):
        """Items with only 'en' localization return the English name."""
        from repositories.sde_repo import _get_localized_name_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        # COALESCE(NULL, en_name) returns en_name when requested lang is missing
        mock_result.fetchone.return_value = ("Retriever Refined Resourcer SKIN",)
        conn.execute.return_value = mock_result

        result = _get_localized_name_impl(engine, 91108, "zh")
        assert result == "Retriever Refined Resourcer SKIN"


class TestGetLocalizedNames:
    def test_returns_dict_for_batch(self):
        from repositories.sde_repo import _get_localized_names_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchall.return_value = [(18, "斜長岩"), (34, "三鈦合金")]
        conn.execute.return_value = mock_result

        result = _get_localized_names_impl(engine, [18, 34], "ja")
        assert result == {18: "斜長岩", 34: "三鈦合金"}

    def test_returns_empty_dict_for_empty_input(self):
        from repositories.sde_repo import _get_localized_names_impl

        engine, conn = _mock_engine()
        result = _get_localized_names_impl(engine, [], "zh")
        assert result == {}
        conn.execute.assert_not_called()

    def test_partial_results(self):
        from repositories.sde_repo import _get_localized_names_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchall.return_value = [(18, "Plagioklas")]
        conn.execute.return_value = mock_result

        result = _get_localized_names_impl(engine, [18, 99999999], "de")
        assert result == {18: "Plagioklas"}
        assert 99999999 not in result

    def test_batch_falls_back_to_english(self):
        """Items missing the requested language get English names via COALESCE."""
        from repositories.sde_repo import _get_localized_names_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            (18, "斜长石"),  # has zh translation
            (91108, "Retriever Refined Resourcer SKIN"),  # en fallback
        ]
        conn.execute.return_value = mock_result

        result = _get_localized_names_impl(engine, [18, 91108], "zh")
        assert result[18] == "斜长石"
        assert result[91108] == "Retriever Refined Resourcer SKIN"


class TestGetAllTranslations:
    def test_returns_all_languages(self):
        from repositories.sde_repo import _get_all_translations_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ("de", "Plagioklas"),
            ("en", "Plagioclase"),
            ("fr", "Plagioclase"),
            ("ja", "斜長岩"),
            ("ko", "사장석"),
            ("ru", "Плагиоклаз"),
            ("zh", "斜长石"),
        ]
        conn.execute.return_value = mock_result

        result = _get_all_translations_impl(engine, 18)
        assert len(result) == 7
        assert result["zh"] == "斜长石"
        assert result["en"] == "Plagioclase"

    def test_returns_empty_dict_when_not_found(self):
        from repositories.sde_repo import _get_all_translations_impl

        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        conn.execute.return_value = mock_result

        result = _get_all_translations_impl(engine, 99999999)
        assert result == {}


class TestEnglishFallbackSQL:
    """Verify COALESCE/JOIN fallback against a real SQLite engine."""

    def test_single_returns_localized_when_available(self, sqlite_engine):
        from repositories.sde_repo import _get_localized_name_impl

        assert _get_localized_name_impl(sqlite_engine, 18, "zh") == "斜长岩"

    def test_single_falls_back_to_english(self, sqlite_engine):
        from repositories.sde_repo import _get_localized_name_impl

        result = _get_localized_name_impl(sqlite_engine, 91108, "zh")
        assert result == "Retriever Refined Resourcer SKIN"

    def test_single_returns_none_for_unknown_type(self, sqlite_engine):
        from repositories.sde_repo import _get_localized_name_impl

        assert _get_localized_name_impl(sqlite_engine, 99999, "zh") is None

    def test_batch_mixes_localized_and_fallback(self, sqlite_engine):
        from repositories.sde_repo import _get_localized_names_impl

        result = _get_localized_names_impl(sqlite_engine, [18, 91108], "zh")
        assert result[18] == "斜长岩"
        assert result[91108] == "Retriever Refined Resourcer SKIN"

    def test_batch_excludes_unknown_types(self, sqlite_engine):
        from repositories.sde_repo import _get_localized_names_impl

        result = _get_localized_names_impl(sqlite_engine, [18, 99999], "zh")
        assert 18 in result
        assert 99999 not in result
