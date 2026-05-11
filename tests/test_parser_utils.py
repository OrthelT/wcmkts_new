"""Tests for services.parser_utils — the EFT + multibuy parser.

Pure unit tests with no DB / Streamlit. Focused on diff-touched paths:
loaded-charge stripping, _is_pure_int_token, _parse_space_separated_line,
and the single-column delegation in _parse_multibuy_line.
"""

from domain.pricer import SlotType
from services.parser_utils import (
    _is_pure_int_token,
    _parse_eft_item_line,
    _parse_multibuy_line,
    _parse_space_separated_line,
    parse_eft_fitting,
    parse_multibuy_text,
)


# =============================================================================
# _parse_eft_item_line — loaded-charge stripping
# =============================================================================


def test_eft_line_module_with_loaded_charge_drops_charge():
    item = _parse_eft_item_line("Heavy Pulse Laser II, Multifrequency M", SlotType.HIGH)
    assert item is not None
    assert item.name == "Heavy Pulse Laser II"
    assert item.quantity == 1


def test_eft_line_module_without_charge_unchanged():
    item = _parse_eft_item_line("Heavy Pulse Laser II", SlotType.HIGH)
    assert item is not None
    assert item.name == "Heavy Pulse Laser II"


def test_eft_line_only_comma_returns_none():
    assert _parse_eft_item_line(",", SlotType.HIGH) is None


def test_eft_line_offline_marker_stripped():
    item = _parse_eft_item_line("Damage Control II /offline", SlotType.LOW)
    assert item is not None
    assert item.name == "Damage Control II"


def test_eft_line_x_suffix_parsed_as_quantity():
    item = _parse_eft_item_line("Hammerhead II x5", SlotType.DRONE)
    assert item is not None
    assert item.name == "Hammerhead II"
    assert item.quantity == 5


def test_eft_line_charge_stripped_before_quantity_suffix_check():
    item = _parse_eft_item_line("Heavy Missile Launcher II, Scourge Fury Heavy Missile", SlotType.HIGH)
    assert item is not None
    assert item.name == "Heavy Missile Launcher II"
    assert item.quantity == 1


def test_eft_full_fitting_drops_charges():
    eft = """[Caracal, Test Fit]
Damage Control II

10MN Afterburner II

Heavy Missile Launcher II, Scourge Fury Heavy Missile
Heavy Missile Launcher II, Scourge Fury Heavy Missile
"""
    result = parse_eft_fitting(eft)
    names = [i.name for i in result.items]
    assert "Caracal" in names
    assert "Heavy Missile Launcher II" in names
    assert not any(n.startswith("Scourge") for n in names), (
        f"charge leaked into fit: {names}"
    )
    launcher = next(i for i in result.items if i.name == "Heavy Missile Launcher II")
    assert launcher.quantity == 2


# =============================================================================
# _is_pure_int_token
# =============================================================================


def test_is_pure_int_plain_digits():
    assert _is_pure_int_token("166") is True


def test_is_pure_int_empty_token_false():
    assert _is_pure_int_token("") is False


def test_is_pure_int_thousands_comma():
    assert _is_pure_int_token("1,000") is True
    assert _is_pure_int_token("12,345") is True


def test_is_pure_int_thousands_period_three_digits():
    assert _is_pure_int_token("1.000") is True
    assert _is_pure_int_token("12.345") is True


def test_is_pure_int_period_decimal_two_digits_false():
    assert _is_pure_int_token("1.50") is False


def test_is_pure_int_period_decimal_four_digits_false():
    assert _is_pure_int_token("1.2345") is False


def test_is_pure_int_module_name_with_digits_false():
    assert _is_pure_int_token("5MN") is False
    assert _is_pure_int_token("Y-T8") is False
    assert _is_pure_int_token("II") is False


def test_is_pure_int_with_leading_zero():
    assert _is_pure_int_token("0042") is True


# =============================================================================
# _parse_space_separated_line — docstring examples
# =============================================================================


def test_space_separated_simple():
    item = _parse_space_separated_line("Torpedo Launcher II 63")
    assert item is not None
    assert item.name == "Torpedo Launcher II"
    assert item.quantity == 63


def test_space_separated_module_with_digits_in_name():
    item = _parse_space_separated_line("5MN Y-T8 Compact Microwarpdrive 166")
    assert item is not None
    assert item.name == "5MN Y-T8 Compact Microwarpdrive"
    assert item.quantity == 166


def test_space_separated_module_with_quoted_prefix():
    item = _parse_space_separated_line("'Halcyon' Core Equalizer I 38")
    assert item is not None
    assert item.name == "'Halcyon' Core Equalizer I"
    assert item.quantity == 38


def test_space_separated_no_quantity_token_defaults_to_one():
    item = _parse_space_separated_line("Damage Control II")
    assert item is not None
    assert item.name == "Damage Control II"
    assert item.quantity == 1


def test_space_separated_only_quantity_returns_none():
    assert _parse_space_separated_line("42") is None


def test_space_separated_empty_returns_none():
    assert _parse_space_separated_line("") is None
    assert _parse_space_separated_line("   ") is None


def test_space_separated_trailing_tokens_ignored():
    item = _parse_space_separated_line("Tritanium 100 1.50 ISK")
    assert item is not None
    assert item.name == "Tritanium"
    assert item.quantity == 100


# =============================================================================
# _parse_multibuy_line — single-column delegates to space-separated
# =============================================================================


def test_multibuy_single_column_delegates_to_space_parser():
    item = _parse_multibuy_line("Torpedo Launcher II 63", qty_first=False)
    assert item is not None
    assert item.name == "Torpedo Launcher II"
    assert item.quantity == 63


def test_multibuy_tab_separated_name_first():
    item = _parse_multibuy_line("Tritanium\t1000", qty_first=False)
    assert item is not None
    assert item.name == "Tritanium"
    assert item.quantity == 1000


def test_multibuy_tab_separated_qty_first():
    item = _parse_multibuy_line("1000\tTritanium", qty_first=True)
    assert item is not None
    assert item.name == "Tritanium"
    assert item.quantity == 1000


def test_multibuy_text_space_separated_block():
    text = """5MN Y-T8 Compact Microwarpdrive 166
'Halcyon' Core Equalizer I 38
"""
    result = parse_multibuy_text(text)
    names = [(i.name, i.quantity) for i in result.items]
    assert ("5MN Y-T8 Compact Microwarpdrive", 166) in names
    assert ("'Halcyon' Core Equalizer I", 38) in names
    assert result.errors == []
