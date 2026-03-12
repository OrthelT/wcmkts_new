"""Tests for DoctrineRepository type_id-based module and ship stock queries."""

from unittest.mock import MagicMock, patch
import pandas as pd
from domain import ModuleStock, ShipStock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(engine=None):
    """Create a DoctrineRepository with a mock DatabaseConfig."""
    from repositories.doctrine_repo import DoctrineRepository

    db = MagicMock()
    db.engine = engine or MagicMock()
    db.alias = "test"
    return db, DoctrineRepository(db)


def _stock_df(type_id=2048, type_name="Damage Control II", total_stock=500, fits_on_mkt=25):
    return pd.DataFrame([{
        "type_name": type_name,
        "type_id": type_id,
        "total_stock": total_stock,
        "fits_on_mkt": fits_on_mkt,
    }])


def _usage_df():
    return pd.DataFrame([
        {"ship_name": "Hurricane Fleet Issue", "ship_target": 20, "fit_qty": 1},
        {"ship_name": "Ferox", "ship_target": 30, "fit_qty": 2},
    ])


# ---------------------------------------------------------------------------
# get_module_stock_info
# ---------------------------------------------------------------------------

class TestGetModuleStockInfo:
    def test_returns_dataframe_for_valid_type_id(self):
        db, repo = _make_repo()
        expected = _stock_df()

        with patch("pandas.read_sql_query", return_value=expected):
            result = repo.get_module_stock_info(2048)

        assert not result.empty
        assert result.iloc[0]["type_id"] == 2048

    def test_returns_empty_on_exception(self):
        db, repo = _make_repo()
        db.engine.connect.side_effect = Exception("db down")

        result = repo.get_module_stock_info(2048)
        assert result.empty


# ---------------------------------------------------------------------------
# get_module_usage
# ---------------------------------------------------------------------------

class TestGetModuleUsage:
    def test_returns_usage_dataframe(self):
        db, repo = _make_repo()
        expected = _usage_df()

        with patch("pandas.read_sql_query", return_value=expected):
            result = repo.get_module_usage(2048)

        assert len(result) == 2
        assert "ship_name" in result.columns

    def test_returns_empty_on_exception(self):
        db, repo = _make_repo()
        db.engine.connect.side_effect = Exception("db down")

        result = repo.get_module_usage(2048)
        assert result.empty


# ---------------------------------------------------------------------------
# get_module_stock
# ---------------------------------------------------------------------------

class TestGetModuleStock:
    def test_returns_module_stock_model(self):
        db, repo = _make_repo()

        with patch.object(repo, "get_module_stock_info", return_value=_stock_df()):
            with patch.object(repo, "get_module_usage", return_value=_usage_df()):
                result = repo.get_module_stock(2048)

        assert isinstance(result, ModuleStock)
        assert result.type_id == 2048
        assert result.total_stock == 500
        assert len(result.usage) == 2

    def test_returns_none_when_not_found(self):
        db, repo = _make_repo()

        with patch.object(repo, "get_module_stock_info", return_value=pd.DataFrame()):
            result = repo.get_module_stock(99999)

        assert result is None


# ---------------------------------------------------------------------------
# get_multiple_module_stocks
# ---------------------------------------------------------------------------

class TestGetMultipleModuleStocks:
    def test_returns_dict_keyed_by_type_id(self):
        db, repo = _make_repo()
        stock_a = ModuleStock(type_id=100, type_name="Item A", total_stock=10, fits_on_mkt=5)
        stock_b = ModuleStock(type_id=200, type_name="Item B", total_stock=20, fits_on_mkt=10)

        def mock_get(tid):
            return {100: stock_a, 200: stock_b}.get(tid)

        with patch.object(repo, "get_module_stock", side_effect=mock_get):
            result = repo.get_multiple_module_stocks([100, 200, 999])

        assert set(result.keys()) == {100, 200}
        assert result[100].type_name == "Item A"
        assert result[200].type_name == "Item B"


# ---------------------------------------------------------------------------
# get_ship_stock
# ---------------------------------------------------------------------------

class TestGetShipStock:
    def test_returns_ship_stock_model(self):
        db, repo = _make_repo()
        ship_df = pd.DataFrame([{
            "type_name": "Hurricane Fleet Issue",
            "type_id": 33157,
            "total_stock": 15,
            "fits_on_mkt": 10,
            "fit_id": 494,
        }])

        with patch("pandas.read_sql_query", return_value=ship_df):
            with patch.object(repo, "get_target_by_ship_id", return_value=20):
                with patch("repositories.doctrine_repo._load_preferred_fits", return_value={}):
                    result = repo.get_ship_stock(33157)

        assert isinstance(result, ShipStock)
        assert result.type_id == 33157
        assert result.ship_target == 20

    def test_returns_none_when_not_found(self):
        db, repo = _make_repo()

        with patch("pandas.read_sql_query", return_value=pd.DataFrame()):
            with patch("repositories.doctrine_repo._load_preferred_fits", return_value={}):
                result = repo.get_ship_stock(99999)

        assert result is None

    def test_uses_preferred_fit_id(self):
        db, repo = _make_repo()
        ship_df = pd.DataFrame([{
            "type_name": "Ferox Navy Issue",
            "type_id": 72812,
            "total_stock": 5,
            "fits_on_mkt": 3,
            "fit_id": 473,
        }])

        with patch("pandas.read_sql_query", return_value=ship_df) as mock_query:
            with patch.object(repo, "get_target_by_ship_id", return_value=10):
                with patch("repositories.doctrine_repo._load_preferred_fits", return_value={72812: 473}):
                    result = repo.get_ship_stock(72812)

        assert result is not None
        assert result.fit_id == 473
        # Verify the SQL included fit_id parameter
        call_args = mock_query.call_args
        params = call_args[1].get("params") or call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("params", {})
        assert params.get("fit_id") == 473


# ---------------------------------------------------------------------------
# get_multiple_ship_stocks
# ---------------------------------------------------------------------------

class TestGetMultipleShipStocks:
    def test_returns_dict_keyed_by_type_id(self):
        db, repo = _make_repo()
        stock_a = ShipStock(type_id=100, type_name="Ship A", total_stock=5, fits_on_mkt=3)
        stock_b = ShipStock(type_id=200, type_name="Ship B", total_stock=10, fits_on_mkt=7)

        def mock_get(tid):
            return {100: stock_a, 200: stock_b}.get(tid)

        with patch.object(repo, "get_ship_stock", side_effect=mock_get):
            result = repo.get_multiple_ship_stocks([100, 200, 999])

        assert set(result.keys()) == {100, 200}


# ---------------------------------------------------------------------------
# _load_preferred_fits
# ---------------------------------------------------------------------------

class TestLoadPreferredFits:
    def test_parses_string_keys_to_ints(self):
        from repositories.doctrine_repo import _load_preferred_fits

        mock_toml = {
            "preferred_fits": {
                "72812": 473,
                "33157": 494,
            }
        }

        with patch("builtins.open", MagicMock()):
            with patch("tomllib.load", return_value=mock_toml):
                with patch("pathlib.Path.exists", return_value=True):
                    # Clear streamlit cache for this test
                    result = _load_preferred_fits.__wrapped__()

        assert result == {72812: 473, 33157: 494}
        assert all(isinstance(k, int) for k in result)
        assert all(isinstance(v, int) for v in result.values())
