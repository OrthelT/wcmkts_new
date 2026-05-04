import pandas as pd
import requests
import streamlit as st
from millify import millify

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from repositories import get_market_repository, get_sde_repository
from services import get_build_cost_service, get_jita_price
from state import get_active_language
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from services.type_name_localization import get_localized_name_map
from pages.components.header import render_page_title

logger = setup_logging(__name__)


def is_valid_image_url(url: str) -> bool:
    """Check whether an item image URL resolves to an image."""
    try:
        response = requests.head(url, timeout=5)
        return response.status_code == 200 and "image" in response.headers.get(
            "content-type", ""
        )
    except Exception as exc:
        logger.error("Error checking image URL %s: %s", url, exc)
        return False


def _format_isk(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{millify(value, precision=2)} ISK"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"

    total_seconds = max(int(round(seconds)), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _render_item_filters(catalog: pd.DataFrame, language_code: str) -> tuple[pd.DataFrame, int, int]:
    categories = sorted(catalog["category_name"].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox(
        translate_text(language_code, "build_costs.category_label"),
        categories,
        help=translate_text(language_code, "build_costs.category_help"),
    )

    category_df = catalog[catalog["category_name"] == selected_category]
    groups = sorted(category_df["group_name"].dropna().unique().tolist())
    selected_group = st.sidebar.selectbox(
        translate_text(language_code, "build_costs.group_label"),
        groups,
    )

    group_df = category_df[category_df["group_name"] == selected_group].copy()
    group_df = group_df.sort_values(by="type_name").reset_index(drop=True)

    base_type_name_map = {
        int(row.type_id): row.type_name
        for row in group_df[["type_id", "type_name"]].itertuples(index=False)
    }
    localized_name_map = get_localized_name_map(
        list(base_type_name_map.keys()),
        get_sde_repository(),
        language_code,
        logger,
    )
    group_df["type_name"] = group_df["type_id"].map(
        lambda type_id: localized_name_map.get(int(type_id), base_type_name_map[int(type_id)])
    )
    group_df = group_df.sort_values(by="type_name").reset_index(drop=True)

    type_name_map = {
        int(row.type_id): row.type_name
        for row in group_df[["type_id", "type_name"]].itertuples(index=False)
    }
    selected_type_id = st.sidebar.selectbox(
        translate_text(language_code, "build_costs.item_label"),
        list(type_name_map.keys()),
        format_func=lambda type_id: type_name_map.get(int(type_id), str(type_id)),
    )

    quantity = int(
        st.sidebar.number_input(
            translate_text(language_code, "build_costs.quantity_label"),
            min_value=1,
            value=1,
            help=translate_text(language_code, "build_costs.quantity_help"),
        )
    )
    return group_df, selected_type_id, quantity


def _render_price_summaries(
    language_code: str,
    market_name: str,
    market_price: float | None,
    jita_price: float | None,
    build_cost_per_unit: float,
) -> None:
    if market_price:
        profit_per_unit = market_price - build_cost_per_unit
        percent_profit = ((market_price - build_cost_per_unit) / market_price) * 100
        st.markdown(
            translate_text(
                language_code,
                "build_costs.market_price_summary",
                market_name=market_name,
                price=millify(market_price, precision=2),
                profit=millify(profit_per_unit, precision=2),
                margin=f"{percent_profit:.2f}",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.write(
            translate_text(language_code, "build_costs.no_market_price", market_name=market_name)
        )

    if jita_price:
        profit_per_unit = jita_price - build_cost_per_unit
        percent_profit = ((jita_price - build_cost_per_unit) / jita_price) * 100
        st.markdown(
            translate_text(
                language_code,
                "build_costs.jita_price_summary",
                price=millify(jita_price, precision=2),
                profit=millify(profit_per_unit, precision=2),
                margin=f"{percent_profit:.2f}",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.write(translate_text(language_code, "build_costs.no_jita_price"))


def _build_snapshot_frame(snapshot) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "type_name": snapshot.type_name,
                "category_name": snapshot.category_name,
                "group_name": snapshot.group_name,
                "quantity": snapshot.quantity,
                "total_cost_per_unit": snapshot.total_cost_per_unit,
                "total_cost": snapshot.total_cost,
                "time_per_unit_display": _format_duration(snapshot.time_per_unit),
                "total_time_display": _format_duration(snapshot.total_time),
                "me": snapshot.me,
                "runs": snapshot.runs,
                "fetched_at": snapshot.fetched_at or "N/A",
            }
        ]
    )


def _build_group_frame(group_df: pd.DataFrame) -> pd.DataFrame:
    display_df = pd.DataFrame(
        {
            "type_name": group_df["type_name"],
            "total_cost_per_unit": group_df["total_cost_per_unit"],
            "time_per_unit": group_df["time_per_unit"],
            "me": group_df["me"],
            "runs": group_df["runs"],
            "fetched_at": group_df["fetched_at"],
        }
    )
    display_df["time_per_unit_display"] = display_df["time_per_unit"].map(_format_duration)
    display_df = display_df.drop(columns=["time_per_unit"])
    display_df["fetched_at"] = display_df["fetched_at"].fillna("N/A")
    return pd.DataFrame(display_df).reset_index(drop=True)


def main() -> None:
    language_code = get_active_language()
    market = render_market_selector()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    logger.info("Starting build cost page for market %s", market.database_alias)

    service = get_build_cost_service()
    market_repo = get_market_repository()
    catalog = service.get_available_costs()

    render_page_title(translate_text(language_code, "build_costs.title"))

    st.write(translate_text(language_code, "build_costs.data_source_description"))

    if catalog.empty:
        st.warning(translate_text(language_code, "build_costs.no_cost_data"))
        st.stop()

    group_df, selected_type_id, quantity = _render_item_filters(catalog, language_code)
    snapshot = service.get_cost_snapshot(selected_type_id, quantity=quantity)
    if snapshot is None:
        st.error(
            translate_text(
                language_code,
                "build_costs.no_cost_data_for_item",
                type_id=selected_type_id,
            )
        )
        st.stop()
    assert snapshot is not None
    display_name = snapshot.type_name
    selected_rows = group_df[group_df["type_id"] == selected_type_id]
    if not selected_rows.empty:
        display_name = str(selected_rows["type_name"].iloc[0])

    market_price = market_repo.get_local_price(selected_type_id)
    market_price = float(market_price) if market_price else None
    jita_price = float(get_jita_price(selected_type_id) or 0.0)
    jita_price = jita_price or None

    image_url = f"https://images.evetech.net/types/{selected_type_id}/render?size=256"
    fallback_image_url = f"https://images.evetech.net/types/{selected_type_id}/icon"

    left_col, right_col = st.columns([0.2, 0.8])
    with left_col:
        if is_valid_image_url(image_url):
            st.image(image_url)
        else:
            st.image(fallback_image_url, width="stretch")
    with right_col:
        st.header(
            translate_text(language_code, "build_costs.header", item_name=display_name),
            divider="violet",
        )
        st.write(
            translate_text(
                language_code,
                "build_costs.db_summary",
                item_name=display_name,
                quantity=snapshot.quantity,
                me=snapshot.me if snapshot.me is not None else "N/A",
                runs=snapshot.runs if snapshot.runs is not None else "N/A",
                type_id=snapshot.type_id,
            )
        )

        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric(
                label=translate_text(language_code, "build_costs.metric_build_cost_per_unit"),
                value=_format_isk(snapshot.total_cost_per_unit),
            )
        with metric_cols[1]:
            st.metric(
                label=translate_text(language_code, "build_costs.metric_total_build_cost"),
                value=_format_isk(snapshot.total_cost),
            )
        with metric_cols[2]:
            st.metric(
                label=translate_text(language_code, "build_costs.metric_build_time_per_unit"),
                value=_format_duration(snapshot.time_per_unit),
            )
        with metric_cols[3]:
            st.metric(
                label=translate_text(language_code, "build_costs.metric_total_build_time"),
                value=_format_duration(snapshot.total_time),
            )

        st.caption(
            translate_text(
                language_code,
                "build_costs.cost_updated",
                fetched_at=snapshot.fetched_at
                or translate_text(language_code, "build_costs.not_available"),
            )
        )

    _render_price_summaries(
        language_code,
        market.short_name,
        market_price,
        jita_price,
        snapshot.total_cost_per_unit,
    )

    st.subheader(translate_text(language_code, "build_costs.detail_header"))
    snapshot_df = _build_snapshot_frame(snapshot)
    snapshot_df["type_name"] = display_name
    st.dataframe(
        snapshot_df,
        column_config={
            "type_name": st.column_config.TextColumn(translate_text(language_code, "common.item")),
            "category_name": st.column_config.TextColumn(
                translate_text(language_code, "common.category")
            ),
            "group_name": st.column_config.TextColumn(translate_text(language_code, "common.group")),
            "quantity": st.column_config.NumberColumn(
                translate_text(language_code, "build_costs.column_quantity")
            ),
            "total_cost_per_unit": st.column_config.NumberColumn(
                translate_text(language_code, "build_costs.column_cost_per_unit"),
                format="localized",
            ),
            "total_cost": st.column_config.NumberColumn(
                translate_text(language_code, "build_costs.column_total_cost"),
                format="localized",
            ),
            "time_per_unit_display": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_build_time_per_unit")
            ),
            "total_time_display": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_total_build_time")
            ),
            "me": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_cached_me")
            ),
            "runs": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_cached_runs")
            ),
            "fetched_at": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_fetched_at")
            ),
        },
        hide_index=True,
        width="stretch",
    )

    st.subheader(
        translate_text(language_code, "build_costs.group_catalog_header", group_name=snapshot.group_name)
    )
    st.dataframe(
        _build_group_frame(group_df),
        column_config={
            "type_name": st.column_config.TextColumn(translate_text(language_code, "common.item")),
            "total_cost_per_unit": st.column_config.NumberColumn(
                translate_text(language_code, "build_costs.column_cost_per_unit"),
                format="localized",
            ),
            "time_per_unit_display": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_build_time_per_unit")
            ),
            "me": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_cached_me")
            ),
            "runs": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_cached_runs")
            ),
            "fetched_at": st.column_config.TextColumn(
                translate_text(language_code, "build_costs.column_fetched_at")
            ),
        },
        hide_index=True,
        width="stretch",
    )


if __name__ == "__main__":
    main()
