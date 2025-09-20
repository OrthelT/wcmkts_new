import pandas as pd
import datetime
import streamlit as st
from logging_config import setup_logging
from sqlalchemy import text
import requests
from config import DatabaseConfig
from email.utils import parsedate_to_datetime as _parsedate_tz

mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")

logger = setup_logging(__name__)

def parsedate_to_datetime(data):
    parsed_date_tz = _parsedate_tz(data)
    if parsed_date_tz is None:
        raise ValueError('Invalid date value or format "%s"' % str(data))
    *dtuple, tz = parsed_date_tz
    if tz is None:
        return datetime.datetime(*dtuple[:6])
    return datetime.datetime(*dtuple[:6],
            tzinfo=datetime.timezone(datetime.timedelta(seconds=tz)))

def get_type_name(type_id: int) -> str:
    engine = sde_db.engine
    with engine.connect() as conn:
        stmt = text("SELECT typeName FROM inv_info WHERE typeID = :type_id")
        res = conn.execute(stmt, {"type_id": type_id})
        type_name = res.fetchone()[0] if res.fetchone() is not None else None
    engine.dispose()
    return type_name

def update_targets(fit_id, target_value):
    conn = mkt_db.libsql_sync_connect
    cursor = conn.cursor()
    cursor.execute(f"""UPDATE ship_targets
    SET ship_target = {target_value}
    WHERE fit_id = {fit_id};""")
    conn.commit()
    conn.close()
    logger.info(f"Updated target for fit_id {fit_id} to {target_value}")

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
        print("etag found")
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

    print(response.status_code)
    print(response.headers)

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
        print(f"last modified: {st.session_state.sci_last_modified}")
        print(f"expires: {st.session_state.sci_expires}")

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

if __name__ == "__main__":
    pass