import os
import sys
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple
import pandas as pd
import sqlalchemy as sa
import sqlalchemy.orm as orm
import streamlit as st
import pathlib
import requests

from build_cost_models import Structure, Rig, IndustryIndex
from logging_config import setup_logging
from millify import millify
from db_handler import get_categories, get_groups_for_category, get_types_for_group, get_4H_price

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

build_cost_db = os.path.join("build_cost.db")
build_cost_url = f"sqlite:///{build_cost_db}"
valid_structures = [35827, 35825, 35826]

logger = setup_logging(__name__)

@dataclass
class JobQuery:
    item: str
    runs: int
    me: int
    te: int
    tax: float
    security: str = "NULL_SEC"
    system_cost_bonus: float = 0.0
    

    def __post_init__(self):
        self.item_id = get_type_id(self.item)

    def yield_urls(self):
        """Generator that yields URLs for each structure."""
        structure_generator = yield_structure()
        for structure in structure_generator:
            yield self.construct_url(structure), structure.structure

    def construct_url(self, structure):
        rigs = [structure.rig_1, structure.rig_2, structure.rig_3]
        clean_rigs = [rig for rig in rigs if rig != "0" and rig is not None]

        valid_rigs = get_valid_rigs()
        system_id = structure.system_id
        system_cost_index = get_manufacturing_cost_index(system_id)
    
        clean_rigs = [rig for rig in clean_rigs if rig in valid_rigs]
        clean_rig_ids = [valid_rigs[rig] for rig in clean_rigs]

        formatted_rigs = [f"&rig_id={str(rig)}" for rig in clean_rig_ids]
        rigs = "".join(formatted_rigs)
        url = f"https://api.everef.net/v1/industry/cost?product_id={self.item_id}&runs={self.runs}&me={self.me}&te={self.te}&structure_type_id={structure.structure_type_id}&security={self.security}{rigs}&system_cost_bonus={self.system_cost_bonus}&manufacturing_cost={system_cost_index}&facility_tax={self.tax}"
        return url

def get_structure_data():
    structure_list = []
    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(sa.select(Structure))
        structures = res.fetchall()
        for structure in structures:
            structure_list.append(structure)
    return structure_list   

def get_valid_rigs():
    rigs = fetch_rigs()
    invalid_rigs = [46640, 46641, 46496, 46497, 46634, 46640, 46641]
    valid_rigs = {}
    for k, v in rigs.items():
        if v not in invalid_rigs:
            valid_rigs[k] = v
    return valid_rigs

def fetch_industry_system_cost_indices():
    url = "https://esi.evetech.net/latest/industry/systems/?datasource=tranquility"
    response = requests.get(url)
    response.raise_for_status()

    systems_data = response.json()

    # Flatten data into rows of: system_id, activity, cost_index
    flat_records = []
    for system in systems_data:
        system_id = system['solar_system_id']
        for activity_info in system['cost_indices']:
            flat_records.append({
                'system_id': system_id,
                'activity': activity_info['activity'],
                'cost_index': activity_info['cost_index']
            })

    # Create DataFrame and set MultiIndex for fast lookup
    df = pd.DataFrame(flat_records)
    df.set_index(['system_id', 'activity'], inplace=True)

    return df

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
        logger.info(f"Rig name is 0")
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
        res = conn.execute(sa.select(Structure).where(Structure.structure == structure_name))
        structure = res.fetchall()
        if structure is not None:
            return structure[0]
        else:
            raise Exception(f"No structure found for {structure_name}")
    
def get_manufacturing_cost_index(system_id: int) -> float | None:
   
    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(sa.select(IndustryIndex.manufacturing).where(IndustryIndex.solar_system_id == system_id))
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
        return int(data['typeID'])
    else:
        logger.error(f"Error fetching: {response.status_code}")
        raise Exception(f"Error fetching type id for {type_name}: {response.status_code}")

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

def get_costs(job: JobQuery):
    url_generator = job.yield_urls()
    results = {}
    structures = get_all_structures()
    progress_bar = st.progress(0, text=f"Fetching data from {len(structures)} structures...")
    # Get the longest structure name for padding
    max_length = max(len(str(s.structure)) for s in structures)
    
    for i in range(len(structures)):
        url, structure_name = next(url_generator)
        # Pad the line with spaces to ensure it's at least as long as the previous line
        status = f"\rFetching {i+1} of {len(structures)} structures: {structure_name}"
        progress_bar.progress(i/len(structures), text=status)

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            try:
                data2 = data['manufacturing'][str(job.item_id)]
            except KeyError as e:
                print(e)
                print(f"No data found for {job.item_id}")
                logger.error(f"Error: {e} No data found for {job.item_id}")
                return None
        else:
            logger.error(f"Error fetching data for {structure_name}: {response.status_code}")
            logger.error(f"Error: {response.text}")
            continue

        results[structure_name] = {
            "total_cost": data2['total_cost'],
            "total_cost_per_unit": data2['total_cost_per_unit'],
            "total_material_cost": data2['total_material_cost'],
            "facility_tax": data2['facility_tax'],
            "scc_surcharge": data2['scc_surcharge'],
            "system_cost_index": data2['system_cost_index'],
            "total_job_cost": data2['total_job_cost']
        }
    return results

def get_all_structures() -> Sequence[sa.Row[Tuple[Structure]]]:
    engine = sa.create_engine(build_cost_url)
    with engine.connect() as conn:
        res = conn.execute(sa.select(Structure).filter(Structure.structure_type_id.in_(valid_structures)))
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
        print(data)
        return data[str(type_id)]['sell']['percentile']
    else:
        logger.error(f"Error fetching price for {type_id}: {response.status_code}")
        raise Exception(f"Error fetching price for {type_id}: {response.status_code}")

def main():

      # App title and logo
    # Handle path properly for WSL environment
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"

    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        if image_path.exists():
            st.image(str(image_path), width=150)
        else:
            st.warning("Logo image not found")
    with col2:
        st.title("Build Cost Tool")
        st.text("Experimental Beta Version 0.1")

    df = pd.read_csv("build_catagories.csv")
    df = df.sort_values(by='category')
    categories = df['category'].unique().tolist()

    selected_category = st.sidebar.selectbox("Select a category", categories)

    category_df = df[df['category'] == selected_category]
    category_id = category_df['id'].values[0]
    groups = get_groups_for_category(category_id)
    groups = groups.sort_values(by='groupName')
    group_names = groups['groupName'].unique()
    selected_group = st.sidebar.selectbox("Select a group", group_names)
    group_id = groups[groups['groupName'] == selected_group]['groupID'].values[0]

    types_df = get_types_for_group(group_id)
    types_df = types_df.sort_values(by='typeName')
    type_names = types_df['typeName'].unique()
    selected_item = st.sidebar.selectbox("Select an item", type_names)
    type_id = types_df[types_df['typeName'] == selected_item]['typeID'].values[0]

    runs = st.sidebar.number_input("Runs", min_value=1, max_value=1000000, value=1)
    me = st.sidebar.number_input("ME", min_value=0, max_value=10, value=10)
    te = st.sidebar.number_input("TE", min_value=0, max_value=20, value=10)
    tax = st.sidebar.number_input("Tax (%)", min_value=0.0, max_value=1.0, step=0.1, format="%.1f", value=0.5)
    
    url = f"https://images.evetech.net/types/{type_id}/render?size=256"

    if st.button("Calculate"):
        vale_price = get_4H_price(type_id)
        jita_price = get_jita_price(type_id)
        if jita_price:
            jita_price = float(jita_price)
        else:
            st.write("No Jita price data found for this item")
            
        if vale_price:
            vale_price = float(vale_price)
        else:
            st.write("No Vale price data found for this item")
        if jita_price and vale_price:
            vale_jita_price_ratio = ((vale_price-jita_price) / jita_price) * 100
        else:
            vale_jita_price_ratio = 0
  
        col1, col2 = st.columns([0.2, 0.8])
        with col1:
            st.image(url)
        with col2:
            st.header(f"Calculating cost for {selected_item}", divider="violet")
            st.write(f"Calculating cost for {selected_item} with {runs} runs, {me} ME, {te} TE, {tax}% tax (type_id: {type_id})")

            if vale_price:
                st.write(f"4-HWWF price: {millify(vale_price, precision=2)} ISK ({vale_jita_price_ratio:.2f}% Jita)")
            if jita_price:
                st.write(f"Jita price: {millify(jita_price, precision=2)} ISK")


        job = JobQuery(item=selected_item, 
                    runs=runs, 
                    me=me, 
                    te=te, 
                    tax=tax/100)
        
        results = get_costs(job)

        if results is not None:

            df = pd.DataFrame.from_dict(results, orient='index')
            df = df.sort_values(by='total_cost', ascending=True)
            low_cost = df['total_cost_per_unit'].min()
            low_cost = float(low_cost)
            if vale_price:
                profit_per_unit_vale = vale_price - low_cost
                percent_profit_vale = ((vale_price - low_cost) / vale_price) * 100
                st.metric(label="Profit per unit Vale", value=f"{millify(profit_per_unit_vale, precision=2)} ISK ({percent_profit_vale:.2f}%)")
            else:
                st.write("No Vale price data found for this item")
            if jita_price:
                profit_per_unit_jita = jita_price - low_cost
                percent_profit_jita = ((jita_price - low_cost) / jita_price) * 100
                st.metric(label="Profit per unit Jita", value=f"{millify(profit_per_unit_jita, precision=2)} ISK ({percent_profit_jita:.2f}%)")
            else:
                st.write("No Jita price data found for this item")
           
            df['total_cost'] = df['total_cost'].apply(lambda x: millify(x, precision=2))
            df['total_cost_per_unit'] = df['total_cost_per_unit'].apply(lambda x: millify(x, precision=2))
            df['total_material_cost'] = df['total_material_cost'].apply(lambda x: millify(x, precision=2))
            df['facility_tax'] = df['facility_tax'].apply(lambda x: millify(x, precision=2))
            df['scc_surcharge'] = df['scc_surcharge'].apply(lambda x: millify(x, precision=2))
            df['total_job_cost'] = df['total_job_cost'].apply(lambda x: millify(x, precision=2))
            df['system_cost_index'] = df['system_cost_index'].apply(lambda x: millify(x, precision=2))
            st.dataframe(df)
        else:
            logger.error(f"No results found for {selected_item}")
            raise Exception(f"No results found for {selected_item}")

if __name__ == "__main__":
    main()
