from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import os
import requests
from logging_config import setup_logging

logger = setup_logging(__name__)

def get_type_name(type_id: int) -> str:
    # Prefer sde_lite.db; fall back to sde.db if present
    if os.path.exists("sde_lite.db"):
        sde = "sqlite+libsql:///sde_lite.db"
    else:
        logger.error("No SDE database found (expected sde_lite.db)")
        return None
    sdee_engine = create_engine(sde)
    with Session(bind=sdee_engine) as session:
        try:
            result = session.execute(text("SELECT typeName FROM invTypes as it WHERE it.typeID = :type_id"), {"type_id": type_id})
            row = result.fetchone()
            type_name = row[0] if row is not None else None
            return type_name
        except Exception as e:
            logger.error(f"Error getting type name for type_id={type_id}: {e}")
            return None
def get_type_id_from_sde(type_name: str) -> int:
    if os.path.exists("sde_lite.db"):
        sde = "sqlite+libsql:///sde_lite.db"
    else:
        logger.error("No SDE database found (expected sde_lite.db)")
        return None
    sdee_engine = create_engine(sde)
    with Session(bind=sdee_engine) as session:
        try:
            result = session.execute(text("SELECT typeID FROM invTypes as it WHERE it.typeName = :type_name"), {"type_name": type_name})
            row = result.fetchone()
            type_id = row[0] if row is not None else None
            return type_id
        except Exception as e:
            logger.error(f"Error getting type id for type_name={type_name}: {e}")
            return None

def get_type_id_from_fuzzworks(type_name: str) -> int:
    url = f"https://www.fuzzwork.co.uk/api/typeid.php?typename={type_name}"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        return int(data["typeID"])
    else:
        logger.error(f"Error fetching: {response.status_code}")
        raise Exception(f"Error fetching type id for {type_name}: {response.status_code}")

def get_backup_type_id(type_name: str) -> int:
    logger.warning(f"No type_id found for {type_name}, trying backup methods")
    logger.info("trying sde first")
    type_id = get_type_id_from_sde(type_name)
    if type_id:
        logger.info(f"SDE found type_id for {type_name}: {type_id}")
    else:
        logger.info(f"trying fuzzwork for {type_name}")
        type_id = get_type_id_from_fuzzworks(type_name)
        if type_id:
            logger.info(f"Fuzzwork found type_id for {type_name}: {type_id}")
        else:
            logger.error(f"No type_id found for {type_name}")
            type_id = None
    return type_id

if __name__ == "__main__":
    pass