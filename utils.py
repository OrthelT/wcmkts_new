import pandas as pd
import datetime
import streamlit as st
from logging_config import setup_logging
import requests
from config import DatabaseConfig

mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")

logger = setup_logging(__name__)


def update_industry_index():
    indy_index = fetch_industry_system_cost_indices()
    if indy_index is None:
        logger.info("Industry index current")
        return None
    else:
        engine = build_cost_db.engine
        with engine.connect() as conn:
            indy_index.to_sql("industry_index", conn, if_exists="replace", index=False)
        current_time = datetime.datetime.now().astimezone(datetime.UTC)
        logger.info(f"Industry index updated at {current_time}")

def fetch_industry_system_cost_indices():
    url = "https://esi.evetech.net/latest/industry/systems/?datasource=tranquility"

    if "etag" in st.session_state:
        logger.debug("ETag found; sending If-None-Match")
        headers = {
            "Accept": "application/json",
            "User-Agent": "WC Markets v0.52 (admin contact: Orthel.Toralen@gmail.com; +https://github.com/OrthelT/wcmkts_new",
            "If-None-Match": st.session_state.etag
        }
    else:

        headers = {
            "Accept": "application/json",
            "User-Agent": "WC Markets v0.52 (admin contact: Orthel.Toralen@gmail.com; +https://github.com/OrthelT/wcmkts_new"
        }

    response = requests.get(url, headers=headers)

    logger.debug(f"ESI status: {response.status_code}")
    logger.debug(f"ESI headers: {response.headers}")

    etag = response.headers.get("ETag")

    if response.status_code == 304:
        logger.info("Industry index current, skipping update with status code 304")
        logger.info(f"last modified: {response.headers.get('Last-Modified')}")
        logger.info(f"next_update: {response.headers.get('Expires')}")
        return None

    elif response.status_code == 200:
        systems_data = response.json()
        st.session_state.etag = etag
        st.session_state.sci_last_modified = datetime.datetime.strptime(response.headers.get('Last-Modified'), "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=datetime.timezone.utc)
        st.session_state.sci_expires = datetime.datetime.strptime(response.headers.get('Expires'), "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=datetime.timezone.utc)
        logger.info(f"SCI last modified: {st.session_state.sci_last_modified}")
        logger.info(f"SCI expires: {st.session_state.sci_expires}")

    else:
        response.raise_for_status()

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
    df = df.pivot(index='system_id', columns='activity', values='cost_index')
    df.reset_index(inplace=True)
    df.rename(columns={'system_id': 'solar_system_id'}, inplace=True)

    return df

def get_jita_price(type_id: int) -> float:
    try:
        url = f"https://market.fuzzwork.co.uk/aggregates/?region=10000002&types={type_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data[str(type_id)]["sell"]["percentile"]
        else:
            logger.error(f"Error fetching price for {type_id}: {response.status_code}")
            raise Exception(f"Error fetching price for {type_id}: {response.status_code}")
    except requests.exceptions.ReadTimeout:
        logger.error(f"Timeout fetching price for {type_id}")
        return get_janice_price(type_id)
    except Exception as e:
        logger.error(f"Error fetching price for {type_id}: {e}")
        raise Exception(f"Error fetching price for {type_id}: {e}")

def get_janice_price(type_id: int) -> float:
    api_key = st.secrets.janice.api_key
    url = f"https://janice.e-351.com/api/rest/v2/pricer/{type_id}?market=2"

    headers = {'X-ApiKey': api_key, 'accept': 'application/json'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("top5AveragePrices").get("sellPrice")
    else:
        logger.error(f"Error fetching price for {type_id}: {response.status_code}")
        raise Exception(f"Error fetching price for {type_id}: {response.status_code}")

if __name__ == "__main__":
    pass
