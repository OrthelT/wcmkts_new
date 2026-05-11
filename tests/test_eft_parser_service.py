"""Tests for EFT fitting text parsing."""

from services.eft_parser_service import parse_eft_fit


VEDMAK_FIT = """[Vedmak, lcicles's Vedmak]
1600mm Rolled Tungsten Compact Plates
Damage Control II
Entropic Radiation Sink II
Entropic Radiation Sink II
Multispectrum Energized Membrane II
Multispectrum Energized Membrane II

10MN Y-S8 Compact Afterburner
50MN Y-T8 Compact Microwarpdrive
Remote Sensor Dampener II,Targeting Range Dampening Script
Small F-RX Compact Capacitor Booster,Navy Cap Booster 400

Medium Energy Neutralizer II
Medium Gremlin Compact Energy Neutralizer
Small Infectious Scoped Energy Neutralizer
Heavy Entropic Disintegrator II,Meson Exotic Plasma M

Medium Ancillary Current Router I
Medium Ancillary Current Router II
Medium Trimark Armor Pump II

Hornet EC-300 x4
Hornet EC-300 x1
Warrior II x1
"""


def test_parse_eft_fit_extracts_header_and_aggregates_items():
    result = parse_eft_fit(VEDMAK_FIT)

    assert result.ship_name == "Vedmak"
    assert result.fit_name == "lcicles's Vedmak"
    assert result.item_quantities["Entropic Radiation Sink II"] == 2
    assert result.item_quantities["Multispectrum Energized Membrane II"] == 2
    assert result.item_quantities["Remote Sensor Dampener II"] == 1
    assert result.item_quantities["Targeting Range Dampening Script"] == 1
    assert result.item_quantities["Hornet EC-300"] == 5
    assert result.item_quantities["Warrior II"] == 1


def test_parse_eft_fit_rejects_missing_header():
    try:
        parse_eft_fit("Damage Control II")
    except ValueError as exc:
        assert "header" in str(exc)
    else:
        raise AssertionError("Expected missing header to raise")
