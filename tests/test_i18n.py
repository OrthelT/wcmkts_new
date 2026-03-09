"""Tests for UI translation helpers."""

from ui.i18n import get_language_options, translate_text


def test_get_language_options_includes_spanish():
    assert "es" in get_language_options()


def test_translate_text_formats_spanish_shipping_cost_copy():
    result = translate_text(
        "es",
        "import_helper.description",
        shipping_cost_per_m3="445",
    )

    assert "m3 * 445" in result
    assert "Descubre articulos" in result
