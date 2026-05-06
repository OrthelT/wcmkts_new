"""Tests for shared Streamlit layout styling."""

from unittest.mock import Mock

import pages.components.layout as layout


def test_global_layout_css_removes_default_main_top_padding():
    css = layout.get_global_layout_css()

    assert "[data-testid=\"stMainBlockContainer\"]" in css
    assert ".main .block-container" in css
    assert "padding-top: 1.5rem !important" in css
    assert "position: fixed" not in css
    assert "[data-testid=\"stSidebar\"]::before" not in css


def test_render_global_layout_styles_injects_css(monkeypatch):
    markdown_mock = Mock()

    monkeypatch.setattr(layout.st, "markdown", markdown_mock)

    layout.render_global_layout_styles()

    markdown_mock.assert_called_once_with(layout.get_global_layout_css(), unsafe_allow_html=True)


def test_render_sidebar_branding_uses_sidebar_image(monkeypatch):
    logo_mock = Mock()

    monkeypatch.setattr(layout.st, "logo", logo_mock)

    layout.render_sidebar_branding()

    logo_mock.assert_called_once_with("images/wclogo.png", size="large", icon_image="images/wclogo.png")
