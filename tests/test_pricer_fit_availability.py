"""Tests for compute_fit_availability - the 'Fit Availability' helper.

Pure unit tests: no Streamlit, no DB. Build PricedItem / PricerResult via
dataclass constructors and assert against the returned FitAvailabilitySummary.
"""

import logging

from domain.pricer import (
    InputFormat,
    ParsedItem,
    PricedItem,
    PricerResult,
    SlotType,
)
from services.pricer_service import compute_fit_availability


def _make_item(
    *,
    type_id: int,
    name: str = "Module",
    quantity: int = 1,
    local_sell_volume: int = 0,
    local_sell: float = 0.0,
    slot_type: SlotType = SlotType.LOW,
    category_name: str = "Module",
    has_local_data: bool = True,
) -> PricedItem:
    parsed = ParsedItem(
        type_name=name,
        quantity=quantity,
        type_id=type_id,
        resolved_name=name,
        category_name=category_name,
        slot_type=slot_type,
    )
    return PricedItem(
        image_url=f"https://images.evetech.net/types/{type_id}/icon",
        item=parsed,
        local_sell=local_sell,
        local_sell_volume=local_sell_volume,
        has_local_data=has_local_data,
    )


def _make_result(
    items: list[PricedItem],
    *,
    input_type: InputFormat = InputFormat.EFT,
    fit_name: str = "Test Fit",
    ship_name: str = "Rifter",
) -> PricerResult:
    return PricerResult(
        items=items,
        input_type=input_type,
        fit_name=fit_name,
        ship_name=ship_name,
    )


def test_non_eft_input_returns_empty_summary():
    result = _make_result(
        [_make_item(type_id=1, quantity=1, local_sell_volume=10)],
        input_type=InputFormat.MULTIBUY,
    )

    summary = compute_fit_availability(result)

    assert summary.fits_available == 0
    assert summary.items == ()
    assert summary.bottleneck_items == ()
    assert summary.counted_item_count == 0


def test_empty_fit_returns_empty_summary():
    result = _make_result([])

    summary = compute_fit_availability(result)

    assert summary.fits_available == 0
    assert summary.items == ()
    assert summary.counted_item_count == 0


def test_min_ratio_wins():
    items = [
        _make_item(type_id=1, name="A", quantity=1, local_sell_volume=100),
        _make_item(type_id=2, name="B", quantity=1, local_sell_volume=50),
        _make_item(type_id=3, name="C", quantity=1, local_sell_volume=30),
    ]
    result = _make_result(items)

    summary = compute_fit_availability(result)

    assert summary.fits_available == 30
    assert len(summary.bottleneck_items) == 1
    assert summary.bottleneck_items[0].type_id == 3


def test_zero_stock_blocks_build():
    items = [
        _make_item(type_id=1, name="A", quantity=1, local_sell_volume=100),
        _make_item(type_id=2, name="B", quantity=1, local_sell_volume=0),
    ]
    result = _make_result(items)

    summary = compute_fit_availability(result)

    assert summary.fits_available == 0
    assert len(summary.bottleneck_items) == 1
    assert summary.bottleneck_items[0].type_id == 2


def test_charges_count_by_default():
    items = [
        _make_item(
            type_id=1, name="Hull", quantity=1, local_sell_volume=10,
            slot_type=SlotType.HULL, category_name="Ship",
        ),
        _make_item(
            type_id=2, name="EMP S", quantity=1000, local_sell_volume=0,
            slot_type=SlotType.CARGO,
        ),
    ]
    result = _make_result(items)

    summary = compute_fit_availability(result)

    assert summary.fits_available == 0
    assert any(b.type_id == 2 for b in summary.bottleneck_items)


def test_equivalents_substitution_increases_fits():
    items = [
        _make_item(type_id=1, name="A", quantity=1, local_sell_volume=10),
        _make_item(type_id=2, name="B", quantity=1, local_sell_volume=2),
    ]
    result = _make_result(items)

    raw_summary = compute_fit_availability(result)
    assert raw_summary.fits_available == 2

    aggregated = {2: 50}
    summary = compute_fit_availability(result, aggregated_stock=aggregated)

    assert summary.fits_available == 10
    assert summary.used_equivalents
    item_b = next(i for i in summary.items if i.type_id == 2)
    assert item_b.used_equivalents
    assert item_b.stock_used == 50
    assert item_b.raw_stock == 2


def test_zero_stock_blocks_build(caplog):
    item = _make_item(type_id=1, quantity=1, local_sell_volume=0)
    result = _make_result([item])

    test_logger = logging.getLogger("test_fit_availability_zero_stock")
    with caplog.at_level(logging.WARNING, logger="test_fit_availability_zero_stock"):
        summary = compute_fit_availability(result, logger_instance=test_logger)

    assert summary.fits_available == 0
    assert summary.items[0].fits_possible == 0


def test_bottleneck_tied():
    items = [
        _make_item(type_id=1, name="A", quantity=1, local_sell_volume=5),
        _make_item(type_id=2, name="B", quantity=1, local_sell_volume=5),
        _make_item(type_id=3, name="C", quantity=1, local_sell_volume=100),
    ]
    result = _make_result(items)

    summary = compute_fit_availability(result)

    assert summary.fits_available == 5
    bottleneck_ids = {b.type_id for b in summary.bottleneck_items}
    assert bottleneck_ids == {1, 2}


def test_total_isk_scales_with_fits():
    items = [
        _make_item(type_id=1, quantity=2, local_sell_volume=20, local_sell=100.0),
        _make_item(type_id=2, quantity=1, local_sell_volume=10, local_sell=50.0),
    ]
    result = _make_result(items)

    summary = compute_fit_availability(result)

    expected_per_fit = 2 * 100.0 + 1 * 50.0
    assert summary.total_isk_per_fit == expected_per_fit


def test_ship_type_id_extracted_from_hull():
    ship = _make_item(
        type_id=587, name="Rifter", quantity=1, local_sell_volume=5,
        slot_type=SlotType.HULL, category_name="Ship",
    )
    module = _make_item(type_id=1, quantity=1, local_sell_volume=10)
    result = _make_result([ship, module])

    summary = compute_fit_availability(result)

    assert summary.ship_type_id == 587
    assert summary.ship_name == "Rifter"


def test_ship_type_id_none_when_no_hull_item():
    module = _make_item(type_id=1, quantity=1, local_sell_volume=10)
    result = _make_result([module])

    summary = compute_fit_availability(result)

    assert summary.ship_type_id is None


# =============================================================================
# Partial-data signals: unpriced items, stock_unknown, total_isk_complete
# =============================================================================


def test_unpriced_items_excluded_from_total_and_counted():
    priced = _make_item(type_id=1, quantity=2, local_sell_volume=20, local_sell=100.0)
    unpriced = _make_item(type_id=2, quantity=1, local_sell_volume=10, local_sell=0.0)
    result = _make_result([priced, unpriced])

    summary = compute_fit_availability(result)

    assert summary.total_isk_per_fit == 200.0
    assert summary.unpriced_item_count == 1
    assert summary.total_isk_complete is False


def test_total_isk_complete_when_all_priced():
    items = [
        _make_item(type_id=1, quantity=2, local_sell_volume=20, local_sell=100.0),
        _make_item(type_id=2, quantity=1, local_sell_volume=10, local_sell=50.0),
    ]
    result = _make_result(items)

    summary = compute_fit_availability(result)

    assert summary.unpriced_item_count == 0
    assert summary.total_isk_complete is True


def test_unpriced_logged_via_injected_logger_at_warning(caplog):
    item = _make_item(type_id=1, quantity=1, local_sell_volume=10, local_sell=0.0)
    result = _make_result([item])

    test_logger = logging.getLogger("test_unpriced_logger")
    with caplog.at_level(logging.WARNING, logger="test_unpriced_logger"):
        compute_fit_availability(result, logger_instance=test_logger)

    matching = [r for r in caplog.records if r.name == "test_unpriced_logger"]
    assert any(r.levelno == logging.WARNING for r in matching), (
        f"expected WARNING via injected logger; got {[(r.name, r.levelname) for r in caplog.records]}"
    )
    assert not any(r.levelno == logging.ERROR for r in matching), (
        "unpriced items should log at WARNING, not ERROR"
    )


def test_stock_unknown_when_no_local_data():
    item = _make_item(type_id=1, quantity=1, local_sell_volume=0, has_local_data=False)
    result = _make_result([item])

    summary = compute_fit_availability(result)

    assert summary.items[0].stock_unknown is True
    assert summary.stock_unknown_count == 1


def test_stock_known_when_local_data_present_even_if_zero():
    item = _make_item(type_id=1, quantity=1, local_sell_volume=0, has_local_data=True)
    result = _make_result([item])

    summary = compute_fit_availability(result)

    assert summary.items[0].stock_unknown is False
    assert summary.stock_unknown_count == 0


def test_stock_unknown_overridden_by_aggregated_stock():
    item = _make_item(type_id=1, quantity=1, local_sell_volume=0, has_local_data=False)
    result = _make_result([item])

    summary = compute_fit_availability(result, aggregated_stock={1: 5})

    assert summary.items[0].stock_unknown is False
    assert summary.stock_unknown_count == 0
    assert summary.fits_available == 5


def test_items_with_no_type_id_skipped_silently():
    parsed_no_id = ParsedItem(type_name="Unknown", quantity=1)
    no_id_item = PricedItem(image_url="", item=parsed_no_id, local_sell_volume=10)
    valid_item = _make_item(type_id=2, quantity=1, local_sell_volume=5)
    result = _make_result([no_id_item, valid_item])

    summary = compute_fit_availability(result)

    assert summary.counted_item_count == 1
    assert summary.items[0].type_id == 2
    assert summary.fits_available == 5


def test_floor_rounding_with_qty_greater_than_one():
    item = _make_item(type_id=1, quantity=3, local_sell_volume=10)
    result = _make_result([item])

    summary = compute_fit_availability(result)

    assert summary.fits_available == 3
    assert summary.items[0].fits_possible == 3


def test_zero_quantity_per_fit_returns_zero_fits_possible():
    parsed = ParsedItem(type_name="X", quantity=0, type_id=1, resolved_name="X")
    item = PricedItem(image_url="", item=parsed, local_sell_volume=100, local_sell=10.0)
    result = _make_result([item])

    summary = compute_fit_availability(result)

    assert summary.items[0].fits_possible == 0
    assert summary.fits_available == 0


# =============================================================================
# PricerResult jita-failure signal
# =============================================================================


def test_pricer_result_jita_failure_signal_defaults():
    result = _make_result([])

    assert result.failed_jita_count == 0
    assert result.failed_jita_type_ids == ()
    assert result.jita_provider_failed is False


def test_pricer_result_jita_failure_signal_populated():
    result = PricerResult(
        items=[],
        input_type=InputFormat.EFT,
        failed_jita_type_ids=(1, 2, 3),
    )

    assert result.failed_jita_count == 3
    assert result.jita_provider_failed is True
