from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
import os
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


if __name__ == "__main__":
    pass
