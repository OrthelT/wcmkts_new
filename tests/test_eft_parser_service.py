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


def test_parse_eft_fit_caps_split_at_first_comma_on_anomalous_lines(caplog):
    """A body line with multiple commas must yield at most 2 items, not N.

    EVE's EFT format only uses a single comma per body line (module/charge).
    Capping the split prevents a malformed paste from silently exploding into
    phantom items downstream.
    """
    fit = (
        "[Vedmak, Test]\n"
        "Module Alpha, Charge Beta, Stray Tail\n"
    )

    with caplog.at_level("WARNING", logger="services.eft_parser_service"):
        result = parse_eft_fit(fit)

    assert result.item_quantities == {
        "Module Alpha": 1,
        "Charge Beta, Stray Tail": 1,
    }
    assert any("commas" in record.getMessage() for record in caplog.records), (
        "Expected a WARNING log for the multi-comma anomaly"
    )


def test_parse_eft_fit_handles_module_with_loaded_charge():
    """The canonical 'Module, Charge' EFT syntax must yield both as items."""
    fit = (
        "[Vedmak, Test]\n"
        "Remote Sensor Dampener II, Targeting Range Dampening Script\n"
    )

    result = parse_eft_fit(fit)

    assert result.item_quantities["Remote Sensor Dampener II"] == 1
    assert result.item_quantities["Targeting Range Dampening Script"] == 1


def test_parse_eft_fit_rejects_oversize_text():
    """A 10 MB paste must not hang the worker — bounded by char count."""
    import pytest

    huge = "[Vedmak, Test]\n" + ("Damage Control II\n" * 200_000)
    with pytest.raises(ValueError, match="too large"):
        parse_eft_fit(huge)


def test_parse_eft_fit_rejects_too_many_lines():
    """Thousands of body lines must be rejected — bounded by line count."""
    import pytest

    body = "Damage Control II\n" * 600
    text = "[Vedmak, Test]\n" + body
    with pytest.raises(ValueError, match="too many lines"):
        parse_eft_fit(text)


def test_parse_eft_fit_rejects_too_many_unique_items():
    """A long list of unique modules must be rejected — bounded by unique count."""
    import pytest

    body = "\n".join(f"Module_{i}" for i in range(250))
    text = f"[Vedmak, Test]\n{body}\n"
    with pytest.raises(ValueError, match="too many distinct items"):
        parse_eft_fit(text)
