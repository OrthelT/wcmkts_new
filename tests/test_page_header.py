from unittest.mock import MagicMock, patch

from pages.components import header


def test_render_page_title_no_back_button_by_default():
    with patch.object(header, "st") as mock_st:
        header.render_page_title("My Title")
    mock_st.title.assert_called_once_with("My Title")
    mock_st.button.assert_not_called()
    mock_st.columns.assert_not_called()


def test_render_page_title_renders_back_button_when_back_page_set():
    with patch.object(header, "st") as mock_st:
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        mock_st.button.return_value = False
        header.render_page_title(
            "My Title",
            back_page="pages/market_dashboard.py",
            back_label="← Dashboard",
        )
    mock_st.button.assert_called_once()
    assert mock_st.button.call_args.args[0] == "← Dashboard"
    mock_st.title.assert_called_once_with("My Title")
    mock_st.switch_page.assert_not_called()


def test_render_page_title_back_button_click_switches_page():
    with patch.object(header, "st") as mock_st:
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        mock_st.button.return_value = True
        header.render_page_title("T", back_page="pages/market_dashboard.py")
    mock_st.switch_page.assert_called_once_with("pages/market_dashboard.py")
