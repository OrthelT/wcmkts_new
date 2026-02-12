"""
Market Selector UI Component

Sidebar dropdown that lets the user switch between market hubs.
Returns the active MarketConfig for use in page titles and labels.
"""

import streamlit as st

from domain.market_config import MarketConfig
from settings_service import get_all_market_configs
from state.market_state import get_active_market, get_active_market_key, set_active_market


def render_market_selector() -> MarketConfig:
    """Render a market selector in the sidebar and return the active config.

    When the user picks a different market, ``set_active_market`` is called
    which clears stale services/caches, then triggers ``st.rerun()``.
    """
    configs = get_all_market_configs()
    keys = list(configs.keys())
    names = [configs[k].name for k in keys]

    current_key = get_active_market_key()
    current_idx = keys.index(current_key) if current_key in keys else 0

    selected_name = st.sidebar.selectbox(
        "Market Hub",
        options=names,
        index=current_idx,
        key="market_selector",
    )

    selected_key = keys[names.index(selected_name)]

    if selected_key != current_key:
        set_active_market(selected_key)
        st.rerun()

    return get_active_market()
