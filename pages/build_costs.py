import requests
from state import ss_init
from ui.market_selector import render_market_selector
from ui.formatters import display_build_cost_tool_description
from services import get_jita_price, get_type_resolution_service
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


def display_data(df: pd.DataFrame, selected_structure: str | None = None):
    if selected_structure:
        selected_structure_df = df[df.index == selected_structure]
        selected_total_cost = selected_structure_df["total_cost"].values[0]
        selected_total_cost_per_unit = selected_structure_df[
            "total_cost_per_unit"
        ].values[0]
        st.markdown(
            f"**Selected structure:** <span style='color: orange;'>{
                selected_structure
            }</span> <br>    *Total cost:* <span style='color: orange;'>{
                millify(selected_total_cost, precision=2)
            }</span> <br>    *Cost per unit:* <span style='color: orange;'>{
                millify(selected_total_cost_per_unit, precision=2)
            }</span>",
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
        "_index": st.column_config.TextColumn(label="structure", help="Structure Name"),
        "structure_type": " type",
        "units": st.column_config.NumberColumn(
            "units", help="Number of units built", width=60
        ),
        "total_cost": st.column_config.NumberColumn(
            "total cost",
            help="Total cost of building the units",
            format="localized",
            step=1,
        ),
        "total_cost_per_unit": st.column_config.NumberColumn(
            "cost per unit",
            help="Cost per unit of the item",
            format="localized",
            step=1,
        ),
        "total_material_cost": st.column_config.NumberColumn(
            "material cost", help="Total material cost", format="localized", step=1
        ),
        "total_job_cost": st.column_config.NumberColumn(
            "total job cost",
            help="Total job cost, which includes the facility tax, SCC surcharge, and system cost index",
            format="compact",
        ),
        "facility_tax": st.column_config.NumberColumn(
            "facility tax", help="Facility tax cost", format="compact", width="small"
        ),
        "scc_surcharge": st.column_config.NumberColumn(
            "scc surcharge", help="SCC surcharge cost", format="compact", width="small"
        ),
        "system_cost_index": st.column_config.NumberColumn(
            "cost index", format="compact", width="small"
        ),
        "structure_rigs": st.column_config.ListColumn(
            "rigs",
            help="Rigs fitted to the structure",
        ),
    }

    if selected_structure:
        col_config.update(
            {
                "comparison_cost": st.column_config.NumberColumn(
                    "comparison cost",
                    help="Comparison cost",
                    format="compact",
                    width="small",
                ),
                "comparison_cost_per_unit": st.column_config.NumberColumn(
                    "comparison cost per unit",
                    help="Comparison cost per unit",
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
    results: dict, selected_structure: str, structure_names_for_materials: list
):
    """Display material costs for a selected structure with proper formatting."""
    default_index = 0
    if selected_structure and selected_structure in structure_names_for_materials:
        default_index = structure_names_for_materials.index(selected_structure)

    selected_structure_for_materials = st.selectbox(
        "Select a structure to view material breakdown:",
        structure_names_for_materials,
        index=default_index,
        key="material_structure_selector",
        help="Choose a structure to see detailed material costs and quantities",
    )

    if selected_structure_for_materials not in results:
        st.error(f"No data found for structure: {selected_structure}")
        return

    materials_data = results[selected_structure_for_materials]["materials"]

    type_ids = [int(k) for k in materials_data.keys()]
    type_names = get_type_resolution_service().resolve_type_names(type_ids)
    type_names_dict = {item["id"]: item["name"] for item in type_names}

    materials_list = []
    for type_id_str, material_info in materials_data.items():
        type_id = int(type_id_str)
        type_name = type_names_dict.get(type_id, f"Unknown ({type_id})")

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

    st.subheader(f"Material Breakdown {selected_structure_for_materials}")
    st.markdown(
        f"{
            st.session_state.selected_item_for_display
        } Material Cost: <span style='color: orange;'>**{
            millify(total_material_cost, precision=2)
        } ISK**</span> (*{millify(total_material_volume, precision=2)} m³*) - {
            material_price_source
        }",
        unsafe_allow_html=True,
    )

    column_config = {
        "type_name": st.column_config.TextColumn(
            "Material", help="The name of the material required", width="medium"
        ),
        "quantity": st.column_config.NumberColumn(
            "Quantity",
            help="Amount of material needed",
            format="localized",
            width="small",
        ),
        "volume_per_unit": st.column_config.NumberColumn(
            "Volume/Unit",
            help="Volume per unit of material (m³)",
            format="localized",
            width="small",
        ),
        "volume": st.column_config.NumberColumn(
            "Total Volume",
            help="Total volume of this material (m³)",
            format="localized",
            width="small",
        ),
        "cost_per_unit": st.column_config.NumberColumn(
            "Unit Price",
            help="Cost per unit of material (ISK)",
            format="localized",
            width="small",
        ),
        "cost": st.column_config.NumberColumn(
            "Total Cost",
            help="Total cost for this material (ISK)",
            format="compact",
            width="small",
        ),
        "cost_percentage": st.column_config.NumberColumn(
            "% of Total",
            help="Percentage of total material cost",
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

    st.info(
        "💡 **Tip:** You can download this data as CSV using the download icon (⬇️) in the top-right corner of the table above."
    )


# =============================================================================
# Main Page
# =============================================================================


def main():
    market = render_market_selector()

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
        st.title("Build Cost Tool")

    df = pd.read_csv("csvfiles/build_catagories.csv")
    df = df.sort_values(by="category")
    categories = df["category"].unique().tolist()
    index = categories.index("Ship")

    selected_category = st.sidebar.selectbox(
        "Select a category",
        categories,
        index=index,
        placeholder="Ship",
        help="Select a category to filter the groups and items by.",
    )
    category_df = df[df["category"] == selected_category]
    category_id = category_df["id"].values[0]
    logger.info(f"Selected category: {selected_category} ({category_id})")

    if category_id == 40:
        groups = ["Sovereignty Hub"]
        selected_group = st.sidebar.selectbox("Select a group", groups)
        group_id = 1012
    else:
        groups = get_sde_repository().get_groups_for_category(category_id)
        groups = groups.sort_values(by="groupName")
        groups = groups.drop(groups[groups["groupName"] == "Abyssal Modules"].index)
        group_names = groups["groupName"].unique()
        selected_group = st.sidebar.selectbox("Select a group", group_names)
        group_id = groups[groups["groupName"] == selected_group]["groupID"].values[0]
        logger.info(f"Selected group: {selected_group} ({group_id})")

    try:
        types_df = get_sde_repository().get_types_for_group(group_id)
        types_df = types_df.sort_values(by="typeName")

        if len(types_df) == 0:
            st.warning(f"No items found for group: {selected_group}")
            selected_group = None
            selected_category = "Ship"
            index = categories.index("Ship")
            selected_category = st.sidebar.selectbox(
                "Select a category", categories, index=index
            )
            category_id = df[df["category"] == selected_category]["id"].values[0]
            group_id = 1012
            st.rerun()
        else:
            type_names = types_df["typeName"].unique()
            selected_item = st.sidebar.selectbox("Select an item", type_names)
            type_names_list = type_names.tolist()
    except Exception as e:
        st.warning(f"invalid group: {e}")
        selected_group = None
        selected_category = "Ship"
        index = categories.index("Ship")
        selected_category = st.sidebar.selectbox(
            "Select a category", categories, index=index
        )
        category_id = df[df["category"] == selected_category]["id"].values[0]
        group_id = 1012

    # Only proceed if we have valid data
    if (
        "selected_item" in locals()
        and "type_names_list" in locals()
        and "types_df" in locals()
    ):
        try:
            if selected_item not in type_names_list:
                st.warning(f"Selected item: {selected_item} not a buildable item")
                selected_item = None
            else:
                filtered_df = types_df[types_df["typeName"] == selected_item]
                if len(filtered_df) == 0:
                    st.warning(
                        f"Selected item: {selected_item} not found in types database"
                    )
                    selected_item = None
                else:
                    type_id = filtered_df["typeID"].values[0]
        except Exception as e:
            st.warning(f"invalid item: {e}")
            selected_item = None
            st.rerun()
    else:
        selected_item = None
        type_id = None

    if "type_id" not in locals() or type_id is None:
        st.warning(
            f"Selected item: {
                selected_item if 'selected_item' in locals() else 'None'
            } not a buildable item"
        )
        selected_item = None
        st.rerun()

    runs = st.sidebar.number_input("Runs", min_value=1, max_value=100000, value=1)
    me = st.sidebar.number_input("ME", min_value=0, max_value=10, value=0)
    te = st.sidebar.number_input("TE", min_value=0, max_value=20, value=0)

    st.sidebar.divider()

    price_source = st.sidebar.selectbox(
        "Select a material price source",
        list(PRICE_SOURCE_MAP.keys()),
        help="This is the source of the material prices used in the calculations. ESI Average is the CCP average price used in the in-game industry window, Jita Sell is the minimum price of sale orders in Jita, and Jita Buy is the maximum price of buy orders in Jita.",
    )
    price_source_id = PRICE_SOURCE_MAP[price_source]
    st.session_state.price_source_name = price_source
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

    with st.sidebar.expander("Select a structure to compare (optional)"):
        selected_structure = st.selectbox(
            "Structures:",
            structure_names,
            index=None,
            placeholder="All Structures",
            help="Select a structure to compare the cost to build versus this structure. This is optional and will default to all structures.",
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
        st.session_state.button_label = "Recalculate"
        st.toast(
            "⚠️ Parameters have changed. Click 'Recalculate' to get updated results."
        )
        logger.info("Parameters changed")
    else:
        st.session_state.button_label = "Calculate"

    calculate_clicked = st.sidebar.button(
        st.session_state.button_label,
        type="primary",
        help="Click to calculate the cost for the selected item.",
    )

    if calculate_clicked:
        st.session_state.calculate_clicked = True
        st.session_state.selected_item_for_display = selected_item

    if st.session_state.sci_last_modified:
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"*Industry indexes last updated: {
                st.session_state.sci_last_modified.strftime('%Y-%m-%d %H:%M:%S UTC')
            }*"
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

        progress_bar = st.progress(0, text="Fetching...")
        results, status_log = service.get_costs(
            job,
            progress_callback=lambda c, t, m: progress_bar.progress(
                c / t if t > 0 else 0, text=m
            ),
        )
        logger.debug(
            f"Status log: {status_log['success_count']} success, {
                status_log['error_count']
            } errors"
        )

        if not results:
            st.error(
                "No results returned. This is likely due to problems with the external industry data API. Please try again later."
            )
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
            st.header(f"Build cost for {selected_item}", divider="violet")
            st.write(
                f"Build cost for {selected_item} with {runs} runs, {me} ME, {te} TE, {
                    price_source
                } material price (type_id: {type_id})"
            )

            col1, col2 = st.columns([0.5, 0.5])
            with col1:
                st.metric(
                    label="Build cost per unit",
                    value=f"{millify(low_cost, precision=2)} ISK",
                    help=f"Based on the lowest cost structure: {low_cost_structure}",
                )
                st.markdown(
                    f"**Materials:** {
                        millify(material_cost_per_unit, precision=2)
                    } ISK | **Job cost:** {millify(job_cost_per_unit, precision=2)} ISK"
                )
            with col2:
                st.metric(
                    label="Total Build Cost",
                    value=f"{millify(total_cost, precision=2)} ISK",
                )
                st.markdown(
                    f"**Materials:** {
                        millify(material_cost, precision=2)
                    } ISK | **Job cost:** {millify(job_cost, precision=2)} ISK"
                )

        if vale_price:
            profit_per_unit_vale = vale_price - low_cost
            percent_profit_vale = ((vale_price - low_cost) / vale_price) * 100

            st.markdown(
                f"**{market.short_name} price:** <span style='color: orange;'>{
                    millify(vale_price, precision=2)
                } ISK</span> ( profit: {
                    millify(profit_per_unit_vale, precision=2)
                } ISK |  {percent_profit_vale:.2f}%",
                unsafe_allow_html=True,
            )
        else:
            st.write("No Vale price data found for this item")

        if jita_price:
            profit_per_unit_jita = jita_price - low_cost
            percent_profit_jita = ((jita_price - low_cost) / jita_price) * 100
            st.markdown(
                f"**Jita price:** <span style='color: orange;'>{
                    millify(jita_price, precision=2)
                } ISK</span> (profit: {
                    millify(profit_per_unit_jita, precision=2)
                } ISK | {percent_profit_jita:.2f}%)",
                unsafe_allow_html=True,
            )
        else:
            st.write("No price data found for this item")

        display_df, col_config, col_order = display_data(
            build_cost_df, selected_structure
        )
        st.dataframe(
            display_df,
            column_config=col_config,
            column_order=col_order,
            width="stretch",
        )
        if st.session_state.super:
            st.markdown(
                """
            <span style="font-weight: bold;">Note:
            </span> <span style="color: orange;">
            Only structures configured for supercapital construction displayed.
            </span>
            """,
                unsafe_allow_html=True,
            )

        st.subheader("Material Breakdown")
        results = st.session_state.cost_results
        structure_names_for_materials = sorted(list(results.keys()))
        display_material_costs(
            results, selected_structure, structure_names_for_materials
        )

    else:
        st.subheader("WC Markets Build Cost Tool", divider="violet")
        st.write(
            """
            Find a build cost for an item by selecting a category, group, and
            item in the sidebar. The build cost will be calculated for all
            structures in the database, ordered by cost (lowest to highest)
            along with a table of materials required and their costs for a
            selected structure. You can also select a structure to compare the
            cost to build versus this structure. When you're ready, click the
            'Calculate' button.
            """
        )
        st.markdown(
            display_build_cost_tool_description(),
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
