import os
import sys
from dataclasses import dataclass
from typing import Sequence, Tuple
import pandas as pd
import sqlalchemy as sa
import sqlalchemy.orm as orm
import streamlit as st
import pathlib
import requests
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_cost_models import Structure, Rig, IndustryIndex
from logging_config import setup_logging
from millify import millify
from db_handler import (
    get_groups_for_category,
    get_types_for_group,
    get_4H_price,
    request_type_names,
)
from db_utils import update_industry_index
import datetime

build_cost_db = os.path.join("build_cost.db")
build_cost_url = f"sqlite:///{build_cost_db}"
valid_structures = [35827, 35825, 35826]
super_shipyard_id = 1046452498926

logger = setup_logging(__name__)


@dataclass
class JobQuery:
    item: str
    item_id: int
    group_id: int
    runs: int
    me: int
    te: int
    security: str = "NULL_SEC"
    system_cost_bonus: float = 0.0
    material_prices: str = "ESI_AVG"

    def __post_init__(self):
        if self.group_id in [30, 659]:
            self.super = True
            st.session_state.super = True
            get_all_structures.clear()
        else:
            # clean up the cache, if our last job was a super so all structures can populate again:
            self.super = False
            if st.session_state.super == True:
                get_all_structures.clear()
                st.session_state.super = False

    def yield_urls(self):
        logger.info(f"Super: {st.session_state.super}")
        """Generator that yields URLs for each structure."""
        structure_generator = yield_structure()

        for structure in structure_generator:
            yield self.construct_url(
                structure
            ), structure.structure, structure.structure_type

    def construct_url(self, structure):

        rigs = [structure.rig_1, structure.rig_2, structure.rig_3]
        clean_rigs = [rig for rig in rigs if rig != "0" and rig is not None]

        valid_rigs = get_valid_rigs()
        system_id = structure.system_id
        system_cost_index = get_manufacturing_cost_index(system_id)

        clean_rigs = [rig for rig in clean_rigs if rig in valid_rigs]
        clean_rig_ids = [valid_rigs[rig] for rig in clean_rigs]
        tax = structure.tax

        formatted_rigs = [f"&rig_id={str(rig)}" for rig in clean_rig_ids]
        rigs = "".join(formatted_rigs)
        url = f"https://api.everef.net/v1/industry/cost?product_id={self.item_id}&runs={self.runs}&me={self.me}&te={self.te}&structure_type_id={structure.structure_type_id}&security={self.security}{rigs}&system_cost_bonus={self.system_cost_bonus}&manufacturing_cost={system_cost_index}&facility_tax={tax}&material_prices={self.material_prices}"
        return url


@st.cache_data(ttl=3600)
def get_valid_rigs():
    rigs = fetch_rigs()
    invalid_rigs = [46640, 46641, 46496, 46497, 46634, 46640, 46641]
    valid_rigs = {}
    for k, v in rigs.items():
        if v not in invalid_rigs:
            valid_rigs[k] = v
    return valid_rigs


@st.cache_data(ttl=3600)
def fetch_rigs():
    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(sa.text("SELECT type_name, type_id FROM rigs"))
        res = res.fetchall()
        type_names = [item[0] for item in res]
        type_ids = [item[1] for item in res]

        types_dict = {}
        for name, id in zip(type_names, type_ids):
            types_dict[name] = id
        return types_dict


def fetch_rig_id(rig_name: str | None):
    if rig_name is None:
        return None
    elif rig_name == str(0):
        logger.info("Rig name is 0")
        return None
    else:
        try:
            engine = sa.create_engine(build_cost_url)
            with orm.Session(engine) as session:
                res = session.query(Rig).filter(Rig.type_name == rig_name).one()
                return res.type_id
        except Exception as e:
            logger.error(f"Error fetching rig id for {rig_name}: {e}")
            return None


def fetch_structure_by_name(structure_name: str):
    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(
            sa.select(Structure).where(Structure.structure == structure_name)
        )
        structure = res.fetchall()
        if structure is not None:
            return structure[0]
        else:
            raise Exception(f"No structure found for {structure_name}")


@st.cache_data(ttl=3600)
def get_structure_rigs() -> dict[int, list[int]]:
    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(
            sa.select(
                Structure.structure, Structure.rig_1, Structure.rig_2, Structure.rig_3
            ).where(Structure.structure_type_id.in_(valid_structures))
        )
        rigs = res.fetchall()
        rig_dict = {}
        for rig in rigs:
            structure, rig_1, rig_2, rig_3 = rig
            rig_1 = rig_1 if rig_1 != "0" and rig_1 is not None else None
            rig_2 = rig_2 if rig_2 != "0" and rig_2 is not None else None
            rig_3 = rig_3 if rig_3 != "0" and rig_3 is not None else None
            clean_rigs = [rig for rig in [rig_1, rig_2, rig_3] if rig is not None]
            valid_rigs = get_valid_rigs()
            clean_rig_ids = [
                clean_rigs
                for clean_rigs in clean_rigs
                if clean_rigs in valid_rigs.keys()
            ]
            rig_dict[structure] = clean_rig_ids
        return rig_dict


@st.cache_data(ttl=3600)
def get_manufacturing_cost_index(system_id: int) -> float | None:

    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(
            sa.select(IndustryIndex.manufacturing).where(
                IndustryIndex.solar_system_id == system_id
            )
        )
        index = res.scalar()
        if index is not None:
            return float(index)
        else:
            raise Exception(f"No manufacturing cost index found for {system_id}")


def get_type_id(type_name: str) -> int:
    url = f"https://www.fuzzwork.co.uk/api/typeid.php?typename={type_name}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return int(data["typeID"])
    else:
        logger.error(f"Error fetching: {response.status_code}")
        raise Exception(
            f"Error fetching type id for {type_name}: {response.status_code}"
        )


def get_system_id(system_name: str) -> int:
    engine = sa.create_engine(build_cost_url)
    stmt = sa.select(Structure.system_id).where(Structure.system == system_name)
    with engine.connect() as conn:
        res = conn.execute(stmt)
        system_id = res.scalar()
        if system_id is not None:
            return system_id
        else:
            raise Exception(f"No system id found for {system_name}")


def get_costs(job: JobQuery) -> dict:
    url_generator = job.yield_urls()
    results = {}

    structures = get_all_structures()

    progress_bar = st.progress(
        0, text=f"Fetching data from {len(structures)} structures..."
    )

    for i in range(len(structures)):

        url, structure_name, structure_type = next(url_generator)

        # Pad the line with spaces to ensure it's at least as long as the previous line
        status = f"\rFetching {i+1} of {len(structures)} structures: {structure_name}"
        progress_bar.progress(i / len(structures), text=status)

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            try:
                data2 = data["manufacturing"][str(job.item_id)]
            except KeyError as e:
                logger.error(f"Error: {e} No data found for {job.item_id}")
                logger.error(f"Error: {e} No data found for {job.item_id}")
                return None
        else:
            logger.error(
                f"Error fetching data for {structure_name}: {response.status_code}"
            )
            logger.error(f"Error: {response.text}")
            continue
        units = data2["units"]

        results[structure_name] = {
            "structure_type": structure_type,
            "units": units,
            "total_cost": data2["total_cost"],
            "total_cost_per_unit": data2["total_cost_per_unit"],
            "total_material_cost": data2["total_material_cost"],
            "facility_tax": data2["facility_tax"],
            "scc_surcharge": data2["scc_surcharge"],
            "system_cost_index": data2["system_cost_index"],
            "total_job_cost": data2["total_job_cost"],
            "materials": data2["materials"],  # Include materials data
        }
    return results


@st.cache_data(ttl=3600)
def get_all_structures() -> Sequence[sa.Row[Tuple[Structure]]]:
    engine = sa.create_engine(build_cost_url)
    # handle structure for building supers:
    if st.session_state.super:
        stmt = sa.select(Structure).where(Structure.structure_id == super_shipyard_id)
    else:
        logger.info("not super")
        stmt = (
            sa.select(Structure)
            .where(Structure.structure_id != super_shipyard_id)
            .filter(Structure.structure_type_id.in_(valid_structures))
        )

    with engine.connect() as conn:
        res = conn.execute(stmt)
        structures = res.fetchall()
        return structures


def yield_structure():
    structures = get_all_structures()
    for structure in structures:
        yield structure


def get_jita_price(type_id: int) -> float:
    url = f"https://market.fuzzwork.co.uk/aggregates/?region=10000002&types={type_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data[str(type_id)]["sell"]["percentile"]
    else:
        logger.error(f"Error fetching price for {type_id}: {response.status_code}")
        raise Exception(f"Error fetching price for {type_id}: {response.status_code}")


def filter_commodity_groups():
    df = pd.read_csv("build_catagories.csv")


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
            f"**Selected structure:** <span style='color: orange;'>{selected_structure}</span> <br>    *Total cost:* <span style='color: orange;'>{millify(selected_total_cost, precision=2)}</span> <br>    *Cost per unit:* <span style='color: orange;'>{millify(selected_total_cost_per_unit, precision=2)}</span>",
            unsafe_allow_html=True,
        )
        df["comparison_cost"] = df["total_cost"].apply(
            lambda x: x - selected_total_cost
        )
        df["comparison_cost_per_unit"] = df["total_cost_per_unit"].apply(
            lambda x: x - selected_total_cost_per_unit
        )
        df["comparison_cost"] = df["comparison_cost"].apply(
            lambda x: millify(x, precision=2)
        )
        df["comparison_cost_per_unit"] = df["comparison_cost_per_unit"].apply(
            lambda x: millify(x, precision=2)
        )

    col_order = [
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
        "structure_type": " type",
        "units": st.column_config.NumberColumn(
            "units", help="Number of units built", format="compact", width=60
        ),
        "total_cost": st.column_config.NumberColumn(
            "total cost",
            help="Total cost of building the units",
            format="compact",
            width="small",
        ),
        "total_cost_per_unit": st.column_config.NumberColumn(
            "cost per unit",
            help="Cost per unit of the item",
            format="compact",
            width="small",
        ),
        "total_material_cost": st.column_config.NumberColumn(
            "material cost", help="Total material cost", format="compact", width="small"
        ),
        "total_job_cost": st.column_config.NumberColumn(
            "total job cost",
            help="Total job cost, which includes the facility tax, SCC surcharge, and system cost index",
            format="compact",
            width="small",
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
                "comparison_cost": "comparison cost",
                "comparison_cost_per_unit": "(per unit)",
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


def check_industry_index_expiry():

    now = datetime.datetime.now().astimezone(datetime.UTC)
    if st.session_state.sci_expires:
        expires = st.session_state.sci_expires

        if expires < now:
            logger.info("Industry index expired, updating")
            try:
                update_industry_index()
            except Exception as e:
                logger.error(f"Error updating industry index: {e}")
                raise Exception(f"Error updating industry index: {e}")

    else:
        logger.info("Industry index not in session state, updating")
        try:
            update_industry_index()
        except Exception as e:
            logger.error(f"Error updating industry index: {e}")
            raise Exception(f"Error updating industry index: {e}")


def initialise_session_state():
    logger.info("initialising build cost tool")
    if "sci_expires" not in st.session_state:
        st.session_state.sci_expires = None
    if "sci_last_modified" not in st.session_state:
        st.session_state.sci_last_modified = None
    if "etag" not in st.session_state:
        st.session_state.etag = None
    if "cost_results" not in st.session_state:
        st.session_state.cost_results = None
    if "current_job_params" not in st.session_state:
        st.session_state.current_job_params = None
    if "selected_item_for_display" not in st.session_state:
        st.session_state.selected_item_for_display = None
    if "price_source" not in st.session_state:
        st.session_state.price_source = None
    if "price_source_name" not in st.session_state:
        st.session_state.price_source_name = None
    if "calculate_clicked" not in st.session_state:
        st.session_state.calculate_clicked = False
    if "button_label" not in st.session_state:
        st.session_state.button_label = "Calculate"
    if "current_job_params" not in st.session_state:
        st.session_state.current_job_params = None
    if "selected_structure" not in st.session_state:
        st.session_state.selected_structure = None
    if "super" not in st.session_state:
        st.session_state.super = False
    st.session_state.initialised = True

    try:
        check_industry_index_expiry()
    except Exception as e:
        logger.error(f"Error checking industry index expiry: {e}")


def display_material_costs(results: dict, selected_structure: str, item_id: str):
    """
    Display material costs for a selected structure with proper formatting.

    Args:
        results: Dictionary containing cost calculation results from get_costs
        selected_structure: Name of the selected structure
        item_id: The type_id of the item being manufactured
    """
    if selected_structure not in results:
        st.error(f"No data found for structure: {selected_structure}")
        return

    # Get materials data from results
    materials_data = results[selected_structure]["materials"]

    # Get type names for materials
    type_ids = [int(k) for k in materials_data.keys()]
    type_names = request_type_names(type_ids)
    type_names_dict = {item["id"]: item["name"] for item in type_names}

    # Build materials list
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

    # Create DataFrame
    df = pd.DataFrame(materials_list)
    df = df.sort_values(by="cost", ascending=False)

    # Calculate cost percentage
    total_material_cost = df["cost"].sum()
    total_material_volume = df["volume"].sum()
    material_price_source = st.session_state.price_source_name

    df["cost_percentage"] = df["cost"] / total_material_cost

    # Display header
    st.subheader(f"Material Breakdown - {selected_structure}")
    st.markdown(
        f"**Total Material Cost:** {millify(total_material_cost, precision=2)} ISK ({millify(total_material_volume, precision=2)} m³) - {material_price_source}"
    )

    # Configure columns with proper formatting
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
        # Display the dataframe with custom configuration
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
            use_container_width=True,
        )
    with col2:
        # material cost chart
        st.bar_chart(
            df,
            x="type_name",
            y="cost",
            y_label="",
            x_label="",
            horizontal=True,
            use_container_width=False,
            height=310,
        )

    # Add download tip below the table
    st.info(
        "💡 **Tip:** You can download this data as CSV using the download icon (⬇️) in the top-right corner of the table above."
    )


def main():
    if "initialised" not in st.session_state:
        initialise_session_state()
    else:
        logger.info("Session state already initialised, skipping initialisation")
    logger.info("build cost tool initialised and awaiting user input")

    # Handle path properly for WSL environment
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"

    # App title and logo
    col1, col2 = st.columns([0.2, 0.8])

    with col1:
        if image_path.exists():
            st.image(str(image_path), width=150)
        else:
            st.warning("Logo image not found")
    with col2:
        st.title("Build Cost Tool")

    df = pd.read_csv("build_catagories.csv")
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
        groups = get_groups_for_category(category_id)
        groups = groups.sort_values(by="groupName")
        groups = groups.drop(groups[groups["groupName"] == "Abyssal Modules"].index)
        group_names = groups["groupName"].unique()
        selected_group = st.sidebar.selectbox("Select a group", group_names)
        group_id = groups[groups["groupName"] == selected_group]["groupID"].values[0]
        logger.info(f"Selected group: {selected_group} ({group_id})")

    types_df = get_types_for_group(group_id)
    types_df = types_df.sort_values(by="typeName")
    type_names = types_df["typeName"].unique()
    selected_item = st.sidebar.selectbox("Select an item", type_names)
    type_id = types_df[types_df["typeName"] == selected_item]["typeID"].values[0]

    runs = st.sidebar.number_input("Runs", min_value=1, max_value=1000000, value=1)
    me = st.sidebar.number_input("ME", min_value=0, max_value=10, value=0)
    te = st.sidebar.number_input("TE", min_value=0, max_value=20, value=0)

    st.sidebar.divider()

    price_source = st.sidebar.selectbox(
        "Select a material price source",
        ["ESI Average", "Jita Sell", "Jita Buy"],
        help="This is the source of the material prices used in the calculations. ESI Average is the CCP average price used in the in-game industry window, Jita Sell is the minimum price of sale orders in Jita, and Jita Buy is the maximum price of buy orders in Jita.",
    )

    price_source_dict = {
        "ESI Average": "ESI_AVG",
        "Jita Sell": "FUZZWORK_JITA_SELL_MIN",
        "Jita Buy": "FUZZWORK_JITA_BUY_MAX",
    }
    price_source_id = price_source_dict[price_source]
    logger.info(f"Selected price source: {price_source} ({price_source_id})")

    st.session_state.price_source_name = price_source
    st.session_state.price_source = price_source_id
    logger.info(
        f"Price source: {st.session_state.price_source_name} ({st.session_state.price_source})"
    )

    url = f"https://images.evetech.net/types/{type_id}/render?size=256"
    alt_url = f"https://images.evetech.net/types/{type_id}/icon"

    all_structures = get_all_structures()
    structure_names = [structure.structure for structure in all_structures]
    structure_names = sorted(structure_names)

    with st.sidebar.expander("Select a structure to compare (optional)"):
        selected_structure = st.selectbox(
            "Structures:",
            structure_names,
            index=None,
            placeholder="All Structures",
            help="Select a structure to compare the cost to build versus this structure. This is optional and will default to all structures.",
        )

    # Create job parameters for comparison
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
    logger.info(
        f"st.session_state.calculate_clicked: {st.session_state.calculate_clicked}"
    )

    # Check if parameters have changed (but don't auto-calculate)
    params_changed = (
        st.session_state.current_job_params is not None
        and st.session_state.current_job_params != current_job_params
    )
    logger.info(f"Params changed: {params_changed}")
    if params_changed:
        st.session_state.button_label = "Recalculate"
        st.warning(
            "⚠️ Parameters have changed. Click 'Recalculate' to get updated results."
        )
        logger.info("Parameters changed")
    else:
        st.session_state.button_label = "Calculate"
        logger.info("Parameters not changed")

    calculate_clicked = st.sidebar.button(
        st.session_state.button_label,
        type="primary",
        help="Click to calculate the cost for the selected item.",
    )

    logger.info(f"just passed the click button, calculate_clicked: {calculate_clicked}")

    if calculate_clicked:
        st.session_state.calculate_clicked = True
        logger.info("Calculate button clicked, calculating")
        st.session_state.selected_item_for_display = selected_item

    if st.session_state.sci_last_modified:
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"*Industry indexes last updated: {st.session_state.sci_last_modified.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        )

    if st.session_state.calculate_clicked:
        logger.info("Calculate button clicked, calculating")
        st.session_state.calculate_clicked = False

        job = JobQuery(
            item=st.session_state.selected_item_for_display,
            item_id=type_id,
            group_id=group_id,
            runs=runs,
            me=me,
            te=te,
            material_prices=st.session_state.price_source,
        )

        # Always fetch new results when Calculate is clicked
        results = get_costs(job)

        # Cache the results and parameters
        st.session_state.cost_results = results
        st.session_state.current_job_params = current_job_params
        st.session_state.selected_item_for_display = selected_item

        if results is None:
            logger.error(f"No results found for {selected_item}")
            raise Exception(f"No results found for {selected_item}")

    else:
        logger.info("No calculate clicked, not calculating")

    # Display results if available (either fresh or cached)
    if (
        st.session_state.cost_results is not None
        and st.session_state.selected_item_for_display == selected_item
    ):
        # Get prices for display
        vale_price = get_4H_price(type_id)
        jita_price = get_jita_price(type_id)
        if jita_price:
            jita_price = float(jita_price)
        if vale_price:
            vale_price = float(vale_price)

        results = st.session_state.cost_results

        build_cost_df = pd.DataFrame.from_dict(results, orient="index")

        structure_rigs = get_structure_rigs()
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
                st.image(alt_url, use_container_width=True)
        with col2:
            st.header(f"Build cost for {selected_item}", divider="violet")
            st.write(
                f"Build cost for {selected_item} with {runs} runs, {me} ME, {te} TE, {price_source} material price (type_id: {type_id})"
            )

            col1, col2 = st.columns([0.5, 0.5])
            with col1:
                st.metric(
                    label="Build cost per unit",
                    value=f"{millify(low_cost, precision=2)} ISK",
                    help=f"Based on the lowest cost structure: {low_cost_structure}",
                )
                st.markdown(
                    f"**Materials:** {millify(material_cost_per_unit, precision=2)} ISK | **Job cost:** {millify(job_cost_per_unit, precision=2)} ISK"
                )
            with col2:
                st.metric(
                    label="Total Build Cost",
                    value=f"{millify(total_cost, precision=2)} ISK",
                )
                st.markdown(
                    f"**Materials:** {millify(material_cost, precision=2)} ISK | **Job cost:** {millify(job_cost, precision=2)} ISK"
                )

        if vale_price:
            profit_per_unit_vale = vale_price - low_cost
            percent_profit_vale = ((vale_price - low_cost) / vale_price) * 100

            st.markdown(
                f"**4-HWWF price:** <span style='color: orange;'>{millify(vale_price, precision=2)} ISK</span> ({percent_profit_vale:.2f}% Jita | profit: {millify(profit_per_unit_vale, precision=2)} ISK)",
                unsafe_allow_html=True,
            )

        else:
            st.write("No Vale price data found for this item")

        if jita_price:
            profit_per_unit_jita = jita_price - low_cost
            percent_profit_jita = ((jita_price - low_cost) / jita_price) * 100
            st.markdown(
                f"**Jita price:** <span style='color: orange;'>{millify(jita_price, precision=2)} ISK</span> (profit: {millify(profit_per_unit_jita, precision=2)} ISK {percent_profit_jita:.2f}%)",
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
            use_container_width=True,
        )

        # Material breakdown section - always show if we have results
        st.subheader("Material Breakdown")
        results = st.session_state.cost_results

        structure_names_for_materials = sorted(
            list(results.keys())
        )  # Sort alphabetically

        # Default to the structure selected in sidebar if available
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

        if selected_structure_for_materials:
            # Get the job item_id from current or cached parameters
            if calculate_clicked:
                job = JobQuery(
                    item=selected_item,
                    item_id=type_id,
                    group_id=group_id,
                    runs=runs,
                    me=me,
                    te=te,
                    material_prices=st.session_state.price_source,
                )
                current_item_id = str(job.item_id)
            else:
                cached_job = JobQuery(
                    item=st.session_state.current_job_params["item"],
                    item_id=st.session_state.current_job_params["item_id"],
                    group_id=st.session_state.current_job_params["group_id"],
                    runs=st.session_state.current_job_params["runs"],
                    me=st.session_state.current_job_params["me"],
                    te=st.session_state.current_job_params["te"],
                    material_prices=st.session_state.current_job_params["price_source"],
                )
                current_item_id = str(cached_job.item_id)

            display_material_costs(
                results, selected_structure_for_materials, current_item_id
            )

    else:
        st.subheader("WC Markets Build Cost Tool", divider="violet")
        st.write(
            "Find a build cost for an item by selecting a category, group, and item in the sidebar. The build cost will be calculated for all structures in the database, ordered by cost (lowest to highest) along with a table of materials required and their costs for a selected structure. You can also select a structure to compare the cost to build versus this structure. When you're ready, click the 'Calculate' button."
        )

        st.markdown(
            """

                    - <span style="font-weight: bold; color: orange;">Runs:</span> The number of runs to calculate the cost for.
                    - <span style="font-weight: bold; color: orange;">ME:</span> The material efficiency of the blueprint. (default 0)
                    - <span style="font-weight: bold; color: orange;">TE:</span> The time efficiency of the blueprint. (default 0)
                    - <span style="font-weight: bold; color: orange;">Material price source:</span> The source of the material prices used in the calculations.
                        - *ESI Average* - the CCP average price used in the in-game industry window.
                        - *Jita Sell* - the minimum price of sale orders in Jita.
                        - *Jita Buy* - the maximum price of buy orders in Jita.
                    - <span style="font-weight: bold; color: orange;">Structure:</span> The structure to compare the cost to build versus. (optional)
                    """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    # job = JobQuery(item="11567", item_id=11567, group_id=30, runs=1, me=0, te=0, material_prices="ESI Average")
    # results = get_costs(job)

    main()
