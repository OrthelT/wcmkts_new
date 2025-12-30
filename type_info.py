from typing import Any


from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import os
import requests
from logging_config import setup_logging
from config import DatabaseConfig

logger = setup_logging(__name__)


def get_sde_db():
    return DatabaseConfig("sde")
db = get_sde_db()

class TypeInfo:
    def __init__(self, type_id_or_name: int | str):
        if isinstance(type_id_or_name, int):
            self.type_id = type_id_or_name
            self.type_name = get_type_name(self.type_id)
        elif isinstance(type_id_or_name, str):
            self.type_name = type_id_or_name
            self.type_id = self.get_type_id_from_name(self.type_name)
        self.post_init()

    def post_init(self):
        type_data = self.get_type_data()
        self.group_id = type_data['groupID']
        self.group_name = type_data['groupName']
        self.category_id = type_data['categoryID']
        self.category_name = type_data['categoryName']
        self.volume = type_data['volume']
        self.meta_group_id = type_data['metaGroupID']
        self.meta_group_name = type_data['metaGroupName']

    def get_type_id_from_name(self, type_name: str) -> int | None:
        type_id = get_type_id_from_sde(type_name)
        if type_id:
            logger.debug(f"SDE found type_id for {type_name}: {type_id}")
        else:
            type_id = get_type_id_from_fuzzworks(type_name)
            if type_id:
                logger.debug(f"Fuzzwork found type_id for {type_name}: {type_id}")
            else:
                logger.error(f"No type_id found for {type_name}")
                type_id = None

        return type_id

    def get_type_data(self) -> dict[str, Any]:
        db = get_sde_db()
        with Session(bind=db.engine) as session:
            result = session.execute(text("""SELECT 
            typeID,typeName, groupID, groupName, 
            categoryID, categoryName, volume, metaGroupID, metaGroupName 
            FROM sdeTypes as st WHERE st.typeID = :type_id"""), {"type_id": self.type_id})
            fetched_data = result.fetchone()
            return fetched_data._asdict()

def get_type_name(type_id: int) -> str:
    db = get_sde_db()
    
    with Session(bind=db.engine) as session:
        try:
            result = session.execute(text("SELECT typeName FROM invTypes as it WHERE it.typeID = :type_id"), {"type_id": type_id})
            row = result.fetchone()
            type_name = row[0] if row is not None else None
            return type_name
        except Exception as e:
            logger.error(f"Error getting type name for type_id={type_id}: {e}")
            return None

def get_type_id_from_sde(type_name: str) -> int | None:
    sde_engine = get_sde_db().engine
    with Session(bind=sde_engine) as session:
        try:
            result = session.execute(text("SELECT typeID FROM invTypes as it WHERE it.typeName = :type_name"), {"type_name": type_name})
            row = result.fetchone()
            return row[0] if row is not None else None
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

def get_type_id_with_fallback(type_name: str) -> int | None:
    # Maintained for backwards compatibility, use TypeInfo(name).type_id instead
    type = TypeInfo(type_name)
    type_id = type.get_type_id_from_name(type_name)
    if type_id is None:
        logger.error(f"No type_id found for {type_name}")
        return None
    else:
        return type_id

if __name__ == "__main__":
    pass