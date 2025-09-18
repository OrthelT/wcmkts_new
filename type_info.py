import libsql
from sqlalchemy import text, create_engine, select
from sqlalchemy.orm import Session

sde_db = create_engine("sqlite+libsql:///sde.db")

def get_type_name(type_id: int) -> str:
    with Session(bind=sde_db) as session:
        try:
            result = session.execute(text("SELECT typeName FROM invTypes as it WHERE it.typeID = :type_id"), {"type_id": type_id})
            type_name = result.fetchone()[0]
            return type_name if type_name is not None else None
        except Exception as e:
            print(f"Error getting type name for type_id: {type_id}")
            print(f"Error: {e}")
            return None

def get_type_info(type_id: int)->dict:
    stmt = text("""
        SELECT it.typeName, it.typeID, it.groupID, ig.groupName, ic.categoryID, ic.categoryName
        FROM invTypes it
        JOIN invGroups ig ON it.groupID = ig.groupID
        JOIN invCategories ic ON ig.categoryID = ic.categoryID
        WHERE it.typeID = :type_id
    """)
    with Session(bind=sde_db) as session:
        result = session.execute(stmt, {"type_id": str(type_id)})
        print(result)
        return result.mappings().all()

if __name__ == "__main__":
    pass