"""Tests for page header helpers."""

from unittest.mock import Mock

import pages.components.header as header


def test_render_language_selector_uses_main_widget_by_default(monkeypatch):
    selectbox_mock = Mock(return_value="en")
    sidebar_selectbox_mock = Mock(return_value="en")

    monkeypatch.setattr(header.st, "selectbox", selectbox_mock)
    monkeypatch.setattr(header.st.sidebar, "selectbox", sidebar_selectbox_mock)

    result = header.render_language_selector("en")

    assert result == "en"
    selectbox_mock.assert_called_once()
    sidebar_selectbox_mock.assert_not_called()


def test_render_language_selector_uses_sidebar_widget_when_requested(monkeypatch):
    selectbox_mock = Mock(return_value="en")
    sidebar_selectbox_mock = Mock(return_value="ja")
    set_active_language_mock = Mock()
    set_language_query_param_mock = Mock()
    rerun_mock = Mock()

    monkeypatch.setattr(header.st, "selectbox", selectbox_mock)
    monkeypatch.setattr(header.st.sidebar, "selectbox", sidebar_selectbox_mock)
    monkeypatch.setattr(header, "set_active_language", set_active_language_mock)
    monkeypatch.setattr(header, "set_language_query_param", set_language_query_param_mock)
    monkeypatch.setattr(header.st, "rerun", rerun_mock)

    result = header.render_language_selector("en", sidebar=True)

    assert result == "ja"
    sidebar_selectbox_mock.assert_called_once()
    selectbox_mock.assert_not_called()
    set_active_language_mock.assert_called_once_with("ja")
    set_language_query_param_mock.assert_called_once_with("ja")
    rerun_mock.assert_called_once()


def test_render_page_header_renders_logo_and_title(monkeypatch):
    class DummyColumn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    columns_mock = Mock(return_value=(DummyColumn(), DummyColumn()))
    image_mock = Mock()
    markdown_mock = Mock()
    title_mock = Mock()

    monkeypatch.setattr(header.st, "columns", columns_mock)
    monkeypatch.setattr(header.st, "image", image_mock)
    monkeypatch.setattr(header.st, "title", title_mock)

    header.render_page_header("Import Helper")

    columns_mock.assert_called_once()
    image_mock.assert_called_once()
    title_mock.assert_called_once_with("Import Helper")
    markdown_mock.assert_not_called()


def test_render_page_title_renders_title_and_subtitle(monkeypatch):
    title_mock = Mock()
    markdown_mock = Mock()

    monkeypatch.setattr(header.st, "title", title_mock)
    monkeypatch.setattr(header.st, "markdown", markdown_mock)

    header.render_page_title("Import Helper", subtitle="*Subtitle*")

    title_mock.assert_called_once_with("Import Helper")
    markdown_mock.assert_called_once_with("*Subtitle*")


def test_render_page_header_without_logo_uses_streamlit_title(monkeypatch):
    title_mock = Mock()
    columns_mock = Mock()
    image_mock = Mock()
    markdown_mock = Mock()

    monkeypatch.setattr(header.st, "title", title_mock)
    monkeypatch.setattr(header.st, "columns", columns_mock)
    monkeypatch.setattr(header.st, "image", image_mock)
    monkeypatch.setattr(header.st, "markdown", markdown_mock)

    header.render_page_header("Import Helper", show_logo=False)

    title_mock.assert_called_once_with("Import Helper")
    columns_mock.assert_not_called()
    image_mock.assert_not_called()
    markdown_mock.assert_not_called()
