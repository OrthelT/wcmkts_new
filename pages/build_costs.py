import requests
from state import get_active_language, ss_init
from ui.market_selector import render_market_selector
from init_db import ensure_market_db_ready
from ui.formatters import display_build_cost_tool_description
from ui.i18n import translate_text
from services import get_jita_price, get_type_resolution_service
from services.type_name_localization import get_localized_name_map
from repositories import get_sde_repository, get_market_repository
from repositories.build_cost_repo import get_build_cost_repository
from services.build_cost_service import (
    BuildCostJob,
    BuildCostService,
    get_build_cost_service,
    PRICE_SOURCE_MAP,
)
from logging_config import setup_logging
import os
import sys
import pathlib

import pandas as pd
import streamlit as st
from millify import millify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


logger = setup_logging(__name__)

PRICE_SOURCE_TRANSLATION_KEYS = {
    "ESI Average": "build_costs.price_source_esi_average",
    "Jita Sell": "build_costs.price_source_jita_sell",
    "Jita Buy": "build_costs.price_source_jita_buy",
}


# =============================================================================
# UI Helpers
# =============================================================================


def is_valid_image_url(url: str) -> bool:
    """Check if the URL returns a valid image."""
    try:
        response = requests.head(url)
        return response.status_code == 200 and "image" in response.headers.get(
            "content-type", ""
        )
    except Exception as e:
        logger.error(f"Error checking image URL {url}: {e}")
        return False


def _get_price_source_label(price_source: str, language_code: str) -> str:
    key = PRICE_SOURCE_TRANSLATION_KEYS.get(price_source)
    return translate_text(language_code, key) if key else price_source


def _format_progress_text(current: int, total: int, message: str, language_code: str) -> str:
    if current == 0:
        return translate_text(language_code, "build_costs.progress_start", total=total)

    if ": " in message:
        _, structure_name = message.split(": ", 1)
        return translate_text(
            language_code,
            "build_costs.progress_fetching",
            current=current,
            total=total,
            structure=structure_name,
        )

    return message


def display_data(
    df: pd.DataFrame, language_code: str, selected_structure: str | None = None
):
    if selected_structure:
        selected_structure_df = df[df.index == selected_structure]
        selected_total_cost = selected_structure_df["total_cost"].values[0]
        selected_total_cost_per_unit = selected_structure_df[
            "total_cost_per_unit"
        ].values[0]
        st.markdown(
            (
                f"**{translate_text(language_code, 'build_costs.selected_structure')}:** "
                f"<span style='color: orange;'>{selected_structure}</span> <br>"
                f"*{translate_text(language_code, 'build_costs.column_total_cost')}:* "
                f"<span style='color: orange;'>{millify(selected_total_cost, precision=2)}</span> <br>"
                f"*{translate_text(language_code, 'build_costs.column_cost_per_unit')}:* "
                f"<span style='color: orange;'>"
                f"{millify(selected_total_cost_per_unit, precision=2)}</span>"
            ),
            unsafe_allow_html=True,
        )

        df["comparison_cost"] = df["total_cost"].apply(
            lambda x: x - selected_total_cost
        )
        df["comparison_cost_per_unit"] = df["total_cost_per_unit"].apply(
            lambda x: x - selected_total_cost_per_unit
        )

    col_order = [
        "_index",
        "structure_type",
        "units",
        "total_cost",
        "total_cost_per_unit",
        "total_material_cost",
        "total_job_cost",
        "facility_tax",
        "scc_surcharge",
        "system_cost_index",
        "structure_rigs",
    ]
    if selected_structure:
        col_order.insert(2, "comparison_cost")
        col_order.insert(3, "comparison_cost_per_unit")

    col_config = {
        "_index": st.column_config.TextColumn(
            label=translate_text(language_code, "build_costs.column_structure"),
            help=translate_text(language_code, "build_costs.column_structure_help"),
        ),
        "structure_type": translate_text(language_code, "build_costs.column_structure_type"),
        "units": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_units"),
            help=translate_text(language_code, "build_costs.column_units_help"),
            width=60,
        ),
        "total_cost": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_total_cost"),
            help=translate_text(language_code, "build_costs.column_total_cost_help"),
            format="localized",
            step=1,
        ),
        "total_cost_per_unit": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_cost_per_unit"),
            help=translate_text(language_code, "build_costs.column_cost_per_unit_help"),
            format="localized",
            step=1,
        ),
        "total_material_cost": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_material_cost"),
            help=translate_text(language_code, "build_costs.column_material_cost_help"),
            format="localized",
            step=1,
        ),
        "total_job_cost": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_total_job_cost"),
            help=translate_text(language_code, "build_costs.column_total_job_cost_help"),
            format="compact",
        ),
        "facility_tax": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_facility_tax"),
            help=translate_text(language_code, "build_costs.column_facility_tax_help"),
            format="compact",
            width="small",
        ),
        "scc_surcharge": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_scc_surcharge"),
            help=translate_text(language_code, "build_costs.column_scc_surcharge_help"),
            format="compact",
            width="small",
        ),
        "system_cost_index": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_system_cost_index"),
            format="compact",
            width="small",
        ),
        "structure_rigs": st.column_config.ListColumn(
            translate_text(language_code, "build_costs.column_rigs"),
            help=translate_text(language_code, "build_costs.column_rigs_help"),
        ),
    }

    if selected_structure:
        col_config.update(
            {
                "comparison_cost": st.column_config.NumberColumn(
                    translate_text(language_code, "build_costs.column_comparison_cost"),
                    help=translate_text(language_code, "build_costs.column_comparison_cost_help"),
                    format="compact",
                    width="small",
                ),
                "comparison_cost_per_unit": st.column_config.NumberColumn(
                    translate_text(
                        language_code, "build_costs.column_comparison_cost_per_unit"
                    ),
                    help=translate_text(
                        language_code, "build_costs.column_comparison_cost_per_unit_help"
                    ),
                    format="compact",
                    width="small",
                ),
            }
        )
    df = style_dataframe(df, selected_structure)

    return df, col_config, col_order


def style_dataframe(df: pd.DataFrame, selected_structure: str | None = None):
    df = df.style.apply(
        lambda x: [
            (
                "background-color: lightgreen; color: blue"
                if x.name == selected_structure
                else ""
            )
            for i in x.index
        ],
        axis=1,
    )
    return df


# =============================================================================
# Session State & Industry Index
# =============================================================================


def initialise_session_state():
    logger.info("initialising build cost tool")
    ss_init(
        {
            "sci_expires": None,
            "sci_last_modified": None,
            "etag": None,
            "cost_results": None,
            "current_job_params": None,
            "selected_item_for_display": None,
            "price_source": None,
            "price_source_name": None,
            "calculate_clicked": False,
            "button_label": "Calculate",
            "selected_structure": None,
            "super": False,
        }
    )
    st.session_state.initialised = True

    try:
        check_industry_index_expiry()
    except Exception as e:
        logger.error(f"Error checking industry index expiry: {e}")


def check_industry_index_expiry():
    """Check and refresh the industry index using the service layer."""
    service = get_build_cost_service()
    result = service.check_and_update_industry_index(
        expires=st.session_state.sci_expires,
        etag=st.session_state.etag,
    )
    if result[0] is not None:
        st.session_state.sci_last_modified = result[0]
        st.session_state.sci_expires = result[1]
        st.session_state.etag = result[2]


# =============================================================================
# Material Breakdown Fragment
# =============================================================================


@st.fragment()
def display_material_costs(
    results: dict,
    selected_structure: str,
    structure_names_for_materials: list,
    display_item_name: str,
    language_code: str,
):
    """Display material costs for a selected structure with proper formatting."""
    default_index = 0
    if selected_structure and selected_structure in structure_names_for_materials:
        default_index = structure_names_for_materials.index(selected_structure)

    selected_structure_for_materials = st.selectbox(
        translate_text(language_code, "build_costs.material_breakdown_selector"),
        structure_names_for_materials,
        index=default_index,
        key="material_structure_selector",
        help=translate_text(language_code, "build_costs.material_breakdown_selector_help"),
    )

    if selected_structure_for_materials not in results:
        st.error(
            translate_text(
                language_code,
                "build_costs.material_breakdown_missing",
                structure=selected_structure_for_materials,
            )
        )
        return

    materials_data = results[selected_structure_for_materials]["materials"]

    type_ids = [int(k) for k in materials_data.keys()]
    type_names = get_type_resolution_service().resolve_type_names(type_ids)
    type_names_dict = {item["id"]: item["name"] for item in type_names}
    sde_repo = get_sde_repository()
    localized_type_names = get_localized_name_map(type_ids, sde_repo, language_code, logger)

    materials_list = []
    for type_id_str, material_info in materials_data.items():
        type_id = int(type_id_str)
        type_name = localized_type_names.get(
            type_id,
            type_names_dict.get(
                type_id,
                translate_text(language_code, "build_costs.unknown_type", type_id=type_id),
            ),
        )

        materials_list.append(
            {
                "type_id": type_id,
                "type_name": type_name,
                "quantity": material_info["quantity"],
                "volume_per_unit": material_info["volume_per_unit"],
                "volume": material_info["volume"],
                "cost_per_unit": material_info["cost_per_unit"],
                "cost": material_info["cost"],
            }
        )

    df = pd.DataFrame(materials_list)
    df = df.sort_values(by="cost", ascending=False)

    total_material_cost = df["cost"].sum()
    total_material_volume = df["volume"].sum()
    material_price_source = st.session_state.price_source_name

    df["cost_percentage"] = df["cost"] / total_material_cost

    st.subheader(
        translate_text(
            language_code,
            "build_costs.material_breakdown_for_structure",
            structure=selected_structure_for_materials,
        )
    )
    st.markdown(
        translate_text(
            language_code,
            "build_costs.material_breakdown_summary",
            item=display_item_name,
            cost=millify(total_material_cost, precision=2),
            volume=millify(total_material_volume, precision=2),
            price_source=material_price_source,
        ),
        unsafe_allow_html=True,
    )

    column_config = {
        "type_name": st.column_config.TextColumn(
            translate_text(language_code, "common.item"),
            help=translate_text(language_code, "build_costs.column_material_help"),
            width="medium",
        ),
        "quantity": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_quantity"),
            help=translate_text(language_code, "build_costs.column_quantity_help"),
            format="localized",
            width="small",
        ),
        "volume_per_unit": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_volume_per_unit"),
            help=translate_text(language_code, "build_costs.column_volume_per_unit_help"),
            format="localized",
            width="small",
        ),
        "volume": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_total_volume"),
            help=translate_text(language_code, "build_costs.column_total_volume_help"),
            format="localized",
            width="small",
        ),
        "cost_per_unit": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_unit_price"),
            help=translate_text(language_code, "build_costs.column_unit_price_help"),
            format="localized",
            width="small",
        ),
        "cost": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_total_cost"),
            help=translate_text(language_code, "build_costs.column_total_cost_materials_help"),
            format="compact",
            width="small",
        ),
        "cost_percentage": st.column_config.NumberColumn(
            translate_text(language_code, "build_costs.column_percent_total"),
            help=translate_text(language_code, "build_costs.column_percent_total_help"),
            format="percent",
            width="small",
        ),
    }
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(
            df,
            column_config=column_config,
            column_order=[
                "type_name",
                "quantity",
                "volume_per_unit",
                "volume",
                "cost_per_unit",
                "cost",
                "cost_percentage",
            ],
            hide_index=True,
            width="stretch",
        )
    with col2:
        st.bar_chart(
            df,
            x="type_name",
            y="cost",
            y_label="",
            x_label="",
            horizontal=True,
            width="content",
            height=310,
        )

    st.info(translate_text(language_code, "build_costs.material_breakdown_tip"))


# =============================================================================
# Main Page
# =============================================================================


def main():
    language_code = get_active_language()
    market = render_market_selector()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    logger.info("=" * 80)
    logger.info("Starting build cost tool")
    logger.info("=" * 80)

    if "initialised" not in st.session_state:
        initialise_session_state()
    else:
        logger.info("Session state already initialised, skipping initialisation")
    logger.info("build cost tool initialised and awaiting user input")

    repo = get_build_cost_repository()
    service = get_build_cost_service()

    # App title and logo
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        if image_path.exists():
            st.image(str(image_path), width=150)
    with col2:
        st.title(translate_text(language_code, "build_costs.title"))

    df = pd.read_csv("csvfiles/build_catagories.csv")
    df = df.sort_values(by="category")
    categories = df["category"].unique().tolist()
    index = categories.index("Ship")

    selected_category = st.sidebar.selectbox(
        translate_text(language_code, "build_costs.category_label"),
        categories,
        index=index,
        placeholder=translate_text(language_code, "build_costs.category_placeholder"),
        help=translate_text(language_code, "build_costs.category_help"),
    )
    category_df = df[df["category"] == selected_category]
    category_id = category_df["id"].values[0]
    logger.info(f"Selected category: {selected_category} ({category_id})")

    if category_id == 40:
        groups = ["Sovereignty Hub"]
        selected_group = st.sidebar.selectbox(
            translate_text(language_code, "build_costs.group_label"),
            groups,
            format_func=lambda group: (
                translate_text(language_code, "build_costs.special_group_sovereignty_hub")
                if group == "Sovereignty Hub"
                else group
            ),
        )
        group_id = 1012
    else:
        groups = get_sde_repository().get_groups_for_category(category_id)
        groups = groups.sort_values(by="groupName")
        groups = groups.drop(groups[groups["groupName"] == "Abyssal Modules"].index)
        group_names = groups["groupName"].unique()
        selected_group = st.sidebar.selectbox(
            translate_text(language_code, "build_costs.group_label"), group_names
        )
        group_id = groups[groups["groupName"] == selected_group]["groupID"].values[0]
        logger.info(f"Selected group: {selected_group} ({group_id})")

    try:
        sde_repo = get_sde_repository()
        types_df = sde_repo.get_types_for_group(group_id)
        types_df = types_df.sort_values(by="typeName")

        if len(types_df) == 0:
            st.warning(
                translate_text(
                    language_code,
                    "build_costs.no_buildable_items",
                    group_name=selected_group,
                )
            )
            logger.warning(f"No types returned for group {group_id} — possible missing SDE table")
            st.stop()
        else:
            types_df = types_df.drop_duplicates(subset=["typeID"], keep="first")
            type_id_options = types_df["typeID"].astype(int).tolist()
            type_name_map = dict(zip(type_id_options, types_df["typeName"], strict=False))
            localized_type_names = get_localized_name_map(
                type_id_options, sde_repo, language_code, logger
            )
            selected_type_id = st.sidebar.selectbox(
                translate_text(language_code, "build_costs.item_label"),
                type_id_options,
                format_func=lambda item_type_id: localized_type_names.get(
                    item_type_id, type_name_map[item_type_id]
                ),
            )
            selected_item = type_name_map[selected_type_id]
            selected_item_display = localized_type_names.get(selected_type_id, selected_item)
            type_names_list = list(type_name_map.values())
    except Exception as e:
        st.error(
            translate_text(language_code, "build_costs.load_items_error", error=str(e))
        )
        logger.error(f"Exception loading types for group {group_id}: {e}")
        st.stop()

    # Only proceed if we have valid data
    if (
        "selected_item" in locals()
        and "type_names_list" in locals()
        and "types_df" in locals()
    ):
        try:
            if selected_item not in type_names_list:
                st.warning(
                    translate_text(
                        language_code,
                        "build_costs.invalid_selected_item",
                        item_name=selected_item,
                    )
                )
                selected_item = None
            else:
                filtered_df = types_df[types_df["typeName"] == selected_item]
                if len(filtered_df) == 0:
                    st.warning(
                        translate_text(
                            language_code, "build_costs.item_not_found", item_name=selected_item
                        )
                    )
                    selected_item = None
                else:
                    type_id = filtered_df["typeID"].values[0]
        except Exception as e:
            st.warning(translate_text(language_code, "build_costs.invalid_item", error=str(e)))
            logger.error(f"Exception selecting item: {e}")
            selected_item = None
    else:
        selected_item = None
        selected_item_display = None
        type_id = None

    if "type_id" not in locals() or type_id is None:
        st.warning(
            translate_text(
                language_code,
                "build_costs.select_valid_item",
                item_name=selected_item if "selected_item" in locals() else "None",
            )
        )
        st.stop()

    runs = st.sidebar.number_input(
        translate_text(language_code, "build_costs.runs_label"),
        min_value=1,
        max_value=100000,
        value=1,
    )
    me = st.sidebar.number_input(
        translate_text(language_code, "build_costs.me_label"), min_value=0, max_value=10, value=0
    )
    te = st.sidebar.number_input(
        translate_text(language_code, "build_costs.te_label"), min_value=0, max_value=20, value=0
    )

    st.sidebar.divider()

    price_source = st.sidebar.selectbox(
        translate_text(language_code, "build_costs.material_price_source_label"),
        list(PRICE_SOURCE_MAP.keys()),
        format_func=lambda source: _get_price_source_label(source, language_code),
        help=translate_text(language_code, "build_costs.material_price_source_help"),
    )
    price_source_id = PRICE_SOURCE_MAP[price_source]
    st.session_state.price_source_name = _get_price_source_label(price_source, language_code)
    st.session_state.price_source = price_source_id
    logger.info(f"Selected price source: {price_source} ({price_source_id})")

    url = f"https://images.evetech.net/types/{type_id}/render?size=256"
    alt_url = f"https://images.evetech.net/types/{type_id}/icon"

    # Handle super-mode toggling
    is_super = BuildCostService.is_super_group(group_id)
    if is_super != st.session_state.super:
        st.session_state.super = is_super
        repo.invalidate_structure_caches()

    all_structures = repo.get_all_structures(is_super=st.session_state.super)
    structure_names = sorted([structure.structure for structure in all_structures])

    with st.sidebar.expander(translate_text(language_code, "build_costs.structure_compare_expander")):
        selected_structure = st.selectbox(
            translate_text(language_code, "build_costs.structure_compare_label"),
            structure_names,
            index=None,
            placeholder=translate_text(language_code, "build_costs.structure_compare_placeholder"),
            help=translate_text(language_code, "build_costs.structure_compare_help"),
        )

    current_job_params = {
        "item": selected_item,
        "item_id": type_id,
        "group_id": group_id,
        "runs": runs,
        "me": me,
        "te": te,
        "price_source": st.session_state.price_source,
    }
    logger.info(f"Current job params: {current_job_params}")

    params_changed = (
        st.session_state.current_job_params is not None
        and st.session_state.current_job_params != current_job_params
    )
    if params_changed:
        st.session_state.button_label = translate_text(language_code, "build_costs.recalculate")
        st.toast(translate_text(language_code, "build_costs.parameters_changed"))
        logger.info("Parameters changed")
    else:
        st.session_state.button_label = translate_text(language_code, "build_costs.calculate")

    calculate_clicked = st.sidebar.button(
        st.session_state.button_label,
        type="primary",
        help=translate_text(language_code, "build_costs.calculate_help"),
    )

    if calculate_clicked:
        st.session_state.calculate_clicked = True
        st.session_state.selected_item_for_display = selected_item

    if st.session_state.sci_last_modified:
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"*{translate_text(language_code, 'build_costs.industry_indexes_last_updated', timestamp=st.session_state.sci_last_modified.strftime('%Y-%m-%d %H:%M:%S UTC'))}*"
        )

    if st.session_state.calculate_clicked:
        logger.info("Calculate button clicked, calculating")
        st.session_state.calculate_clicked = False

        job = BuildCostJob(
            item=st.session_state.selected_item_for_display,
            item_id=type_id,
            group_id=group_id,
            runs=runs,
            me=me,
            te=te,
            material_prices=st.session_state.price_source,
        )
        logger.info("=" * 80)

        progress_bar = st.progress(
            0, text=translate_text(language_code, "build_costs.progress_start", total=0)
        )
        results, status_log = service.get_costs(
            job,
            progress_callback=lambda c, t, m: progress_bar.progress(
                c / t if t > 0 else 0,
                text=_format_progress_text(c, t, m, language_code),
            ),
        )
        logger.debug(
            f"Status log: {status_log['success_count']} success, {
                status_log['error_count']
            } errors"
        )

        if not results:
            st.error(translate_text(language_code, "build_costs.no_results"))
            return

        st.session_state.cost_results = results
        st.session_state.current_job_params = current_job_params
        st.session_state.selected_item_for_display = selected_item
        st.rerun()

    # Display results if available
    if (
        st.session_state.cost_results is not None
        and st.session_state.selected_item_for_display == selected_item
    ):
        vale_price = get_market_repository().get_local_price(type_id)
        jita_price = get_jita_price(type_id)
        if jita_price:
            jita_price = float(jita_price)
        if vale_price:
            vale_price = float(vale_price)

        results = st.session_state.cost_results
        selected_item_display = selected_item_display or selected_item

        build_cost_df = pd.DataFrame.from_dict(results, orient="index")

        structure_rigs = repo.get_structure_rigs()
        build_cost_df["structure_rigs"] = build_cost_df.index.map(structure_rigs)
        build_cost_df["structure_rigs"] = build_cost_df["structure_rigs"].apply(
            lambda x: ", ".join(x)
        )

        build_cost_df = build_cost_df.sort_values(by="total_cost", ascending=True)
        total_cost = build_cost_df["total_cost"].min()
        low_cost = build_cost_df["total_cost_per_unit"].min()
        low_cost_structure = build_cost_df["total_cost_per_unit"].idxmin()
        low_cost = float(low_cost)
        material_cost = float(
            build_cost_df.loc[low_cost_structure, "total_material_cost"]
        )
        job_cost = float(build_cost_df.loc[low_cost_structure, "total_job_cost"])
        units = build_cost_df.loc[low_cost_structure, "units"]
        material_cost_per_unit = (
            material_cost / build_cost_df.loc[low_cost_structure, "units"]
        )
        job_cost_per_unit = job_cost / build_cost_df.loc[low_cost_structure, "units"]

        col1, col2 = st.columns([0.2, 0.8])
        with col1:
            if is_valid_image_url(url):
                st.image(url)
            else:
                st.image(alt_url, width="stretch")
        with col2:
            st.header(
                translate_text(
                    language_code, "build_costs.header", item_name=selected_item_display
                ),
                divider="violet",
            )
            st.write(
                translate_text(
                    language_code,
                    "build_costs.summary",
                    item_name=selected_item_display,
                    runs=runs,
                    me=me,
                    te=te,
                    price_source=_get_price_source_label(price_source, language_code),
                    type_id=type_id,
                )
            )

            col1, col2 = st.columns([0.5, 0.5])
            with col1:
                st.metric(
                    label=translate_text(language_code, "build_costs.metric_build_cost_per_unit"),
                    value=f"{millify(low_cost, precision=2)} ISK",
                    help=translate_text(
                        language_code,
                        "build_costs.metric_build_cost_per_unit_help",
                        structure=low_cost_structure,
                    ),
                )
                st.markdown(
                    translate_text(
                        language_code,
                        "build_costs.materials_job_cost",
                        materials=millify(material_cost_per_unit, precision=2),
                        job_cost=millify(job_cost_per_unit, precision=2),
                    )
                )
            with col2:
                st.metric(
                    label=translate_text(language_code, "build_costs.metric_total_build_cost"),
                    value=f"{millify(total_cost, precision=2)} ISK",
                )
                st.markdown(
                    translate_text(
                        language_code,
                        "build_costs.materials_job_cost",
                        materials=millify(material_cost, precision=2),
                        job_cost=millify(job_cost, precision=2),
                    )
                )

        if vale_price:
            profit_per_unit_vale = vale_price - low_cost
            percent_profit_vale = ((vale_price - low_cost) / vale_price) * 100

            st.markdown(
                translate_text(
                    language_code,
                    "build_costs.market_price_summary",
                    market_name=market.short_name,
                    price=millify(vale_price, precision=2),
                    profit=millify(profit_per_unit_vale, precision=2),
                    margin=f"{percent_profit_vale:.2f}",
                ),
                unsafe_allow_html=True,
            )
        else:
            st.write(
                translate_text(
                    language_code, "build_costs.no_market_price", market_name=market.short_name
                )
            )

        if jita_price:
            profit_per_unit_jita = jita_price - low_cost
            percent_profit_jita = ((jita_price - low_cost) / jita_price) * 100
            st.markdown(
                translate_text(
                    language_code,
                    "build_costs.jita_price_summary",
                    price=millify(jita_price, precision=2),
                    profit=millify(profit_per_unit_jita, precision=2),
                    margin=f"{percent_profit_jita:.2f}",
                ),
                unsafe_allow_html=True,
            )
        else:
            st.write(translate_text(language_code, "build_costs.no_jita_price"))

        display_df, col_config, col_order = display_data(
            build_cost_df, language_code, selected_structure
        )
        st.dataframe(
            display_df,
            column_config=col_config,
            column_order=col_order,
            width="stretch",
        )
        if st.session_state.super:
            st.markdown(translate_text(language_code, "build_costs.super_note"), unsafe_allow_html=True)

        st.subheader(translate_text(language_code, "build_costs.material_breakdown"))
        results = st.session_state.cost_results
        structure_names_for_materials = sorted(list(results.keys()))
        display_material_costs(
            results,
            selected_structure,
            structure_names_for_materials,
            selected_item_display,
            language_code,
        )

    else:
        st.subheader(translate_text(language_code, "build_costs.empty_subheader"), divider="violet")
        st.write(translate_text(language_code, "build_costs.empty_description"))
        st.markdown(
            display_build_cost_tool_description(language_code),
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
