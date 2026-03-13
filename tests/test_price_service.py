"""Tests for PriceService caching behavior."""

from types import SimpleNamespace
from unittest.mock import Mock, call, patch


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


class StaticPriceProvider:
    """Provider that returns predefined price results."""

    def __init__(self, name: str, prices: dict[int, tuple[float, float]]):
        self._name = name
        self._prices = prices

    @property
    def name(self) -> str:
        return self._name

    def get_price(self, type_id: int):
        from services.price_service import BatchPriceResult, PriceResult

        return self.get_prices([type_id]).prices.get(
            type_id,
            PriceResult.failure_result(type_id, "Not found"),
        )

    def get_prices(self, type_ids: list[int]):
        from services.price_service import BatchPriceResult, PriceResult, PriceSource

        prices = {}
        failed_ids = []
        for type_id in type_ids:
            if type_id not in self._prices:
                failed_ids.append(type_id)
                continue
            sell_price, buy_price = self._prices[type_id]
            prices[type_id] = PriceResult(
                type_id=type_id,
                sell_price=sell_price,
                buy_price=buy_price,
                source=PriceSource.JITA_FUZZWORK,
                success=sell_price > 0,
            )
        return BatchPriceResult(prices=prices, failed_ids=failed_ids)


def test_price_cache_refreshes_only_after_entry_ttl_expires():
    from services.price_service import PriceService

    provider = DummyPriceProvider()
    service = PriceService(jita_provider=provider, cache_ttl=7200)

    with patch("services.price_service.time.monotonic", side_effect=[100.0, 7299.0, 7301.0, 7301.5]):
        first = service.get_jita_price(34)
        second = service.get_jita_price(34)
        third = service.get_jita_price(34)

    assert first.sell_price == 1.0
    assert second.sell_price == 1.0
    assert third.sell_price == 2.0
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
    assert first.sell_price == 1.0
    assert second.sell_price == 1.0
    assert shared_provider.calls == 1

    price_service_module._PRICE_SERVICES.clear()
    price_service_module._SHARED_JITA_PRICE_CACHE.clear()


def test_fallback_provider_does_not_merge_partial_results():
    from services.price_service import FallbackPriceProvider

    first_provider = StaticPriceProvider("first", {34: (0.0, 5.0)})
    second_provider = StaticPriceProvider("second", {34: (10.0, 0.0)})
    provider = FallbackPriceProvider([first_provider, second_provider])

    result = provider.get_prices([34]).prices[34]

    assert result.sell_price == 10.0
    assert result.buy_price == 0.0


def test_get_jita_prices_dedupes_uncached_type_ids():
    from services.price_service import PriceService

    provider = DummyPriceProvider()
    service = PriceService(jita_provider=provider, cache_ttl=3600)

    result = service.get_jita_prices([34, 34, 35, 35])

    assert sorted(result.prices) == [34, 35]
    assert provider.calls == 2


def test_fuzzwork_provider_chunks_requests_and_sleeps_between_chunks():
    from services.price_service import FuzzworkProvider

    provider = FuzzworkProvider()
    response_payloads = [
        {
            "34": {"sell": {"percentile": 10.0}, "buy": {"percentile": 9.0}},
            "35": {"sell": {"percentile": 20.0}, "buy": {"percentile": 19.0}},
        },
        {
            "36": {"sell": {"percentile": 30.0}, "buy": {"percentile": 29.0}},
            "37": {"sell": {"percentile": 40.0}, "buy": {"percentile": 39.0}},
        },
        {
            "38": {"sell": {"percentile": 50.0}, "buy": {"percentile": 49.0}},
        },
    ]

    responses = []
    for payload in response_payloads:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = payload
        responses.append(response)

    with (
        patch.object(FuzzworkProvider, "BATCH_SIZE", 2),
        patch.object(FuzzworkProvider, "CHUNK_DELAY_SECONDS", 0.2),
        patch("services.price_service.requests.get", side_effect=responses) as mock_get,
        patch("services.price_service.time.sleep") as mock_sleep,
    ):
        result = provider.get_prices([34, 35, 36, 37, 38])

    assert sorted(result.prices) == [34, 35, 36, 37, 38]
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_has_calls([call(0.2), call(0.2)])
