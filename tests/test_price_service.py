"""Tests for PriceService caching behavior."""

from types import SimpleNamespace
from unittest.mock import Mock, patch


class DummyPriceProvider:
    """Simple provider that tracks how many fetches were performed."""

    def __init__(self):
        self.calls = 0

    @property
    def name(self) -> str:
        return "Dummy"

    def get_price(self, type_id: int):
        from services.price_service import PriceResult, PriceSource

        self.calls += 1
        return PriceResult.success_result(type_id, float(self.calls), PriceSource.JITA_FUZZWORK)

    def get_prices(self, type_ids: list[int]):
        from services.price_service import BatchPriceResult

        return BatchPriceResult(prices={type_id: self.get_price(type_id) for type_id in type_ids})


def test_price_cache_refreshes_only_after_entry_ttl_expires():
    from services.price_service import PriceService

    provider = DummyPriceProvider()
    service = PriceService(jita_provider=provider, cache_ttl=7200)

    with patch("services.price_service.time.monotonic", side_effect=[100.0, 7299.0, 7301.0, 7301.5]):
        first = service.get_jita_price(34)
        second = service.get_jita_price(34)
        third = service.get_jita_price(34)

    assert first.price == 1.0
    assert second.price == 1.0
    assert third.price == 2.0
    assert provider.calls == 2


def test_get_price_service_reuses_process_wide_instance_across_calls():
    import services.price_service as price_service_module

    price_service_module._PRICE_SERVICES.clear()
    shared_service = Mock(name="shared_price_service")

    with (
        patch(
            "state.market_state.get_active_market",
            return_value=SimpleNamespace(database_alias="wcmkt"),
        ),
        patch("state.market_state.get_active_market_key", return_value="primary"),
        patch("services.price_service.DatabaseConfig"),
        patch.object(
            price_service_module.PriceService,
            "create_default",
            return_value=shared_service,
        ) as create_default,
    ):
        first = price_service_module.get_price_service()
        second = price_service_module.get_price_service()

    assert first is shared_service
    assert second is shared_service
    assert create_default.call_count == 1
    price_service_module._PRICE_SERVICES.clear()


def test_jita_cache_persists_across_market_switches():
    import services.price_service as price_service_module

    shared_provider = DummyPriceProvider()

    price_service_module._PRICE_SERVICES.clear()
    price_service_module._SHARED_JITA_PRICE_CACHE.clear()

    with (
        patch("services.price_service.DatabaseConfig", return_value=SimpleNamespace()),
        patch("services.price_service.LocalMarketProvider", return_value=Mock()),
        patch("services.price_service.FuzzworkProvider", return_value=shared_provider),
    ):
        b9_service = price_service_module.get_price_service(
            db_alias="wcmktprod",
            market_key="b9",
        )
        first = b9_service.get_jita_price(34)

        h4_service = price_service_module.get_price_service(
            db_alias="wcmktnorth",
            market_key="4h",
        )
        second = h4_service.get_jita_price(34)

    assert b9_service is not h4_service
    assert first.price == 1.0
    assert second.price == 1.0
    assert shared_provider.calls == 1

    price_service_module._PRICE_SERVICES.clear()
    price_service_module._SHARED_JITA_PRICE_CACHE.clear()
