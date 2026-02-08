"""
Tests for SDERepository

Tests the SDE repository _impl functions with mocked engines.
Covers type lookups, group/category queries, table exports, and edge cases.
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock


def _mock_engine():
    """Create a mock engine with context-manager connect()."""
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine = Mock()
    mock_engine.connect.return_value = mock_conn
    return mock_engine, mock_conn


class TestGetTypeName:
    def test_returns_name_when_found(self):
        from repositories.sde_repo import _get_type_name_impl
        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchone.return_value = ("Tritanium",)
        conn.execute.return_value = mock_result

        result = _get_type_name_impl(engine, 34)
        assert result == "Tritanium"

    def test_returns_none_when_not_found(self):
        from repositories.sde_repo import _get_type_name_impl
        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        conn.execute.return_value = mock_result

        result = _get_type_name_impl(engine, 99999999)
        assert result is None

    def test_handles_engine_error(self):
        from repositories.sde_repo import _get_type_name_impl
        engine, conn = _mock_engine()
        conn.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            _get_type_name_impl(engine, 34)


class TestGetTypeId:
    def test_returns_id_when_found(self):
        from repositories.sde_repo import _get_type_id_impl
        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchone.return_value = (34,)
        conn.execute.return_value = mock_result

        result = _get_type_id_impl(engine, "Tritanium")
        assert result == 34

    def test_returns_none_when_not_found(self):
        from repositories.sde_repo import _get_type_id_impl
        engine, conn = _mock_engine()
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        conn.execute.return_value = mock_result

        result = _get_type_id_impl(engine, "NonexistentItem")
        assert result is None


class TestGetGroupsForCategory:
    def test_normal_category_queries_database(self):
        from repositories.sde_repo import _get_groups_for_category_impl
        engine, conn = _mock_engine()
        expected = pd.DataFrame({"groupID": [25], "groupName": ["Frigate"]})

        with patch("pandas.read_sql_query", return_value=expected):
            result = _get_groups_for_category_impl(engine, 6)

        assert len(result) == 1
        assert "groupID" in result.columns

    @patch("pandas.read_csv")
    def test_category_17_reads_from_csv(self, mock_csv):
        from repositories.sde_repo import _get_groups_for_category_impl
        engine, _ = _mock_engine()
        expected = pd.DataFrame({"groupID": [1], "groupName": ["Commodity"]})
        mock_csv.return_value = expected

        result = _get_groups_for_category_impl(engine, 17)

        mock_csv.assert_called_once_with("csvfiles/build_commodity_groups.csv")
        assert len(result) == 1

    def test_category_4_filters_to_group_1136(self):
        from repositories.sde_repo import _get_groups_for_category_impl
        engine, conn = _mock_engine()
        expected = pd.DataFrame({"groupID": [1136], "groupName": ["Ice Product"]})

        with patch("pandas.read_sql_query", return_value=expected) as mock_sql:
            result = _get_groups_for_category_impl(engine, 4)

        # Verify the query contains the group filter
        call_args = mock_sql.call_args
        query_text = str(call_args[0][0])
        assert "1136" in query_text


class TestGetTypesForGroup:
    def test_returns_types_from_local(self):
        from repositories.sde_repo import _get_types_for_group_impl
        engine, conn = _mock_engine()
        remote_engine, _ = _mock_engine()
        expected = pd.DataFrame({"typeID": [34, 35], "typeName": ["Tritanium", "Pyerite"]})

        with patch("pandas.read_sql_query", return_value=expected):
            result = _get_types_for_group_impl(engine, remote_engine, 18)

        assert len(result) == 2

    def test_falls_back_to_remote_on_malformed(self):
        from repositories.sde_repo import _get_types_for_group_impl
        engine, conn = _mock_engine()
        remote_engine, remote_conn = _mock_engine()

        expected = pd.DataFrame({"typeID": [34], "typeName": ["Tritanium"]})

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("database disk image is malformed")
            return expected

        with patch("pandas.read_sql_query", side_effect=side_effect):
            result = _get_types_for_group_impl(engine, remote_engine, 18)

        assert len(result) == 1

    def test_group_332_filters_ram(self):
        from repositories.sde_repo import _get_types_for_group_impl
        engine, conn = _mock_engine()
        remote_engine, _ = _mock_engine()
        data = pd.DataFrame({
            "typeID": [1, 2, 3],
            "typeName": ["R.A.M.- Starship Tech", "R.Db - Foo", "Something Else"],
        })

        with patch("pandas.read_sql_query", return_value=data):
            result = _get_types_for_group_impl(engine, remote_engine, 332)

        assert len(result) == 2
        assert "Something Else" not in result["typeName"].values

    def test_returns_empty_on_both_failures(self):
        from repositories.sde_repo import _get_types_for_group_impl
        engine, conn = _mock_engine()
        remote_engine, remote_conn = _mock_engine()

        with patch("pandas.read_sql_query", side_effect=Exception("no such table: invTypes")):
            result = _get_types_for_group_impl(engine, remote_engine, 18)

        assert result.empty
        assert list(result.columns) == ["typeID", "typeName"]


class TestGetSdeTable:
    def test_valid_table_returns_data(self):
        from repositories.sde_repo import _get_sde_table_impl
        engine, conn = _mock_engine()
        expected = pd.DataFrame({"typeID": [34], "typeName": ["Tritanium"]})

        with patch("pandas.read_sql_query", return_value=expected):
            result = _get_sde_table_impl(engine, "invTypes")

        assert len(result) == 1

    def test_invalid_table_raises_valueerror(self):
        from repositories.sde_repo import _get_sde_table_impl
        engine, _ = _mock_engine()

        with pytest.raises(ValueError, match="Invalid SDE table name"):
            _get_sde_table_impl(engine, "DROP TABLE invTypes; --")


class TestGetTech2TypeIds:
    def test_returns_type_id_list(self):
        from repositories.sde_repo import _get_tech2_type_ids_impl
        engine, conn = _mock_engine()
        expected = pd.DataFrame({"typeID": [11176, 11178, 11184]})

        with patch("pandas.read_sql_query", return_value=expected):
            result = _get_tech2_type_ids_impl(engine)

        assert result == [11176, 11178, 11184]


class TestModuleLevelGetTypeName:
    @patch("repositories.sde_repo.DatabaseConfig")
    def test_returns_name(self, mock_db_cls):
        from repositories.sde_repo import get_type_name
        engine, conn = _mock_engine()
        mock_db = Mock()
        mock_db.engine = engine
        mock_db_cls.return_value = mock_db

        mock_result = Mock()
        mock_result.fetchone.return_value = ("Tritanium",)
        conn.execute.return_value = mock_result

        assert get_type_name(34) == "Tritanium"

    @patch("repositories.sde_repo.DatabaseConfig")
    def test_returns_none_on_error(self, mock_db_cls):
        from repositories.sde_repo import get_type_name
        mock_db_cls.side_effect = Exception("DB init failed")

        assert get_type_name(34) is None
