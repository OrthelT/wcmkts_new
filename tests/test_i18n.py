"""Tests for UI translation helpers."""

from ui.i18n import (
    get_language_label,
    get_language_options,
    translate_text,
)


def test_get_language_options_includes_spanish():
    assert "es" in get_language_options()


def test_get_language_options_include_japanese_and_korean():
    options = get_language_options()

    assert "ja" in options
    assert "ko" in options


def test_get_language_label_uses_flagged_codes():
    assert get_language_label("zh") == "🇨🇳 CN"
    assert get_language_label("ja") == "🇯🇵 JP"


def test_translate_text_formats_spanish_shipping_cost_copy():
    result = translate_text(
        "es",
        "import_helper.column_shipping_help",
        shipping_cost_per_m3="445",
    )

    assert "445" in result
    assert "m3" in result


def test_translate_text_formats_import_helper_caption_copy():
    result = translate_text(
        "en",
        "import_helper.caption_estimated_price",
        color_label="<span>Green</span>",
    )

    assert "Green" in result
    assert "140%" in result


def test_translate_text_formats_build_cost_market_summary():
    result = translate_text(
        "en",
        "build_costs.market_price_summary",
        market_name="4-HWWF",
        price="12.3M",
        profit="2.1M",
        margin="17.07",
    )

    assert "4-HWWF" in result
    assert "12.3M" in result
    assert "17.07%" in result


def test_translate_text_returns_chinese_build_cost_label():
    result = translate_text("zh", "build_costs.material_breakdown")

    assert result == "材料明细"


def test_translate_text_returns_german_build_cost_label():
    result = translate_text("de", "build_costs.material_breakdown")

    assert result == "Materialaufschlüsselung"


def test_translate_text_returns_spanish_build_cost_label():
    result = translate_text("es", "build_costs.material_breakdown")

    assert result == "Desglose de materiales"
