from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import os

def get_type_name(type_id: int) -> str:
    if os.path.exists("sde.db"):
        sde = "sqlite+libsql:///sde.db"
    else:
        raise FileNotFoundError("sde.db not found")
    sdee_engine = create_engine(sde)
    with Session(bind=sdee_engine) as session:
        try:
            result = session.execute(text("SELECT typeName FROM invTypes as it WHERE it.typeID = :type_id"), {"type_id": type_id})
            row = result.fetchone()
            type_name = row[0] if row is not None else None
            return type_name
        except Exception as e:
            print(f"Error getting type name for type_id: {type_id}")
            print(f"Error: {e}")
            return None


if __name__ == "__main__":
    pass