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
