"""
Tests for market_components UI rendering functions.

Focuses on the data-routing contract between the service layer and the
Streamlit components -- specifically that the 7-day and 30-day history frames
returned by ``calculate_30day_metrics`` are forwarded to the top-N display
under the correct labels.
"""
import pandas as pd
from unittest.mock import Mock, MagicMock, patch


def test_30day_metrics_forwards_windows_with_correct_labels():
    """render_30day_metrics_ui must not swap the 7-day and 30-day frames.

    ``calculate_30day_metrics`` returns ``(..., df_30days, df_7days)`` -- the
    30-day frame in slot 5 and the 7-day frame in slot 6. The component must
    forward the true 7-day frame as ``df_7days`` and the true 30-day frame as
    ``df_30days`` to ``render_top_n_items_ui``; otherwise the top-N "this week"
    selector shows 30-day data and vice-versa.
    """
    from pages.components import market_components

    df_30 = pd.DataFrame({"window": ["30d"]})
    df_7 = pd.DataFrame({"window": ["7d"]})

    service = Mock()
    # Service contract: (avg_vol, avg_isk, vol_delta, isk_delta, df_30days, df_7days)
    service.calculate_30day_metrics.return_value = (5.0, 5.0, 1.0, 1.0, df_30, df_7)

    mock_st = MagicMock()
    mock_st.session_state.selected_item = None
    mock_st.columns.side_effect = lambda *a, **k: [MagicMock(), MagicMock()]

    with patch.object(market_components, "st", mock_st), \
            patch.object(market_components, "ss_has", return_value=False), \
            patch.object(market_components, "translate_text", return_value="x"), \
            patch.object(market_components, "render_top_n_items_ui") as mock_top_n:
        market_components.render_30day_metrics_ui(service, language_code="en")

    mock_top_n.assert_called_once()
    kwargs = mock_top_n.call_args.kwargs
    assert kwargs["df_7days"] is df_7, "7-day slot must carry the true 7-day frame"
    assert kwargs["df_30days"] is df_30, "30-day slot must carry the true 30-day frame"


def _make_mock_st(pill_return):
    """Build a wholesale ``st`` mock for render_30day_metrics_ui tests."""
    mock_st = MagicMock()
    mock_st.pills.return_value = pill_return
    mock_st.session_state.selected_item = None
    mock_st.columns.side_effect = lambda *a, **k: [MagicMock(), MagicMock()]
    return mock_st


def _make_service():
    service = Mock()
    # Non-zero metrics so the component renders past the insufficient-data
    # early return; contract: (avg_vol, avg_isk, vol_delta, isk_delta, df_30, df_7)
    service.calculate_30day_metrics.return_value = (
        5.0, 5.0, 1.0, 1.0, pd.DataFrame({"w": ["30d"]}), pd.DataFrame({"w": ["7d"]})
    )
    return service


def test_30day_pill_deselect_preserves_sidebar_category_scope():
    """st.pills returning None (deselect) must behave as "all".

    The sidebar category scope is preserved and no type-id filter is passed
    (``selected_type_ids=None`` means "unused", never an empty scope).
    """
    from pages.components import market_components

    mock_st = _make_mock_st(pill_return=None)
    mock_st.session_state.selected_category = "Ship"
    mock_st.session_state.get.return_value = 6  # selected_category_id
    service = _make_service()

    sidebar_keys = {"selected_category"}
    with patch.object(market_components, "st", mock_st), \
            patch.object(market_components, "ss_has", side_effect=sidebar_keys.__contains__), \
            patch.object(market_components, "translate_text", return_value="x"), \
            patch.object(market_components, "render_top_n_items_ui"):
        market_components.render_30day_metrics_ui(service, language_code="en")

    mock_st.pills.assert_called_once()
    service.get_30day_filter_type_ids.assert_not_called()
    kwargs = service.calculate_30day_metrics.call_args.kwargs
    assert kwargs["selected_category"] == "Ship"
    assert kwargs["selected_category_id"] == 6
    assert kwargs["selected_item_id"] is None
    assert kwargs["selected_type_ids"] is None


def test_30day_pill_selection_overrides_sidebar_category_scope():
    """A selected pill scopes metrics to its type ids and drops the category."""
    from pages.components import market_components

    mock_st = _make_mock_st(pill_return="ships")
    mock_st.session_state.selected_category = "Ship"
    mock_st.session_state.get.return_value = 6  # selected_category_id
    service = _make_service()
    ship_ids = [587, 588, 24698]
    service.get_30day_filter_type_ids.return_value = ship_ids

    sidebar_keys = {"selected_category"}
    with patch.object(market_components, "st", mock_st), \
            patch.object(market_components, "ss_has", side_effect=sidebar_keys.__contains__), \
            patch.object(market_components, "translate_text", return_value="x"), \
            patch.object(market_components, "render_top_n_items_ui"):
        market_components.render_30day_metrics_ui(service, language_code="en")

    service.get_30day_filter_type_ids.assert_called_once_with("ships")
    kwargs = service.calculate_30day_metrics.call_args.kwargs
    assert kwargs["selected_type_ids"] is ship_ids
    assert kwargs["selected_category"] is None
    assert kwargs["selected_category_id"] is None
    assert kwargs["selected_item_id"] is None


def test_30day_pills_hidden_when_item_selected():
    """A selected item skips the pills entirely (item scope wins)."""
    from pages.components import market_components

    mock_st = _make_mock_st(pill_return="ships")
    mock_st.session_state.selected_item_id = 34
    mock_st.session_state.selected_item = "Tritanium"
    service = _make_service()

    item_keys = {"selected_item_id", "selected_item"}
    with patch.object(market_components, "st", mock_st), \
            patch.object(market_components, "ss_has", side_effect=item_keys.__contains__), \
            patch.object(market_components, "translate_text", return_value="x"), \
            patch.object(market_components, "render_top_n_items_ui"):
        market_components.render_30day_metrics_ui(service, language_code="en")

    mock_st.pills.assert_not_called()
    service.get_30day_filter_type_ids.assert_not_called()
    kwargs = service.calculate_30day_metrics.call_args.kwargs
    assert kwargs["selected_item_id"] == 34
    assert kwargs["selected_type_ids"] is None
    assert kwargs["selected_category"] is None
    assert kwargs["selected_category_id"] is None
