"""
Tests for SDERepository localization methods.

Tests the localization _impl functions with mocked engines.
"""

from unittest.mock import Mock


def _mock_engine():
    """Create a mock engine with context-manager connect()."""
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine = Mock()
    mock_engine.connect.return_value = mock_conn
    return mock_engine, mock_conn


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
