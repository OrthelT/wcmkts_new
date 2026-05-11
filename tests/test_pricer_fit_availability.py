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


def test_zero_stock_logged_via_logger(caplog):
    item = _make_item(type_id=1, quantity=1, local_sell_volume=0)
    result = _make_result([item])

    test_logger = logging.getLogger("test_fit_availability")
    with caplog.at_level(logging.WARNING, logger="test_fit_availability"):
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
