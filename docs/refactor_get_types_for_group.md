# Refactor: Dynamic Buildable Items Filtering

## Overview
The function `get_types_for_group` in `db_handler.py` has been refactored to dynamically filter buildable items using the database (`sdelite2.db`) instead of relying on a static CSV file (`industry_types.csv`).

## Motivation
- **Accuracy**: Ensures that only items that can actually be manufactured are listed.
- **Maintenance**: Automatically reflects changes in the SDE (Static Data Export) without manual CSV updates.
- **Consistency**: Uses the same database source as the rest of the application.

## Requirements
To replicate this functionality in another application, the following are required:

1.  **Database**: An SQLite database (e.g., `sdelite2.db`) containing the EVE Online SDE data.
2.  **Tables**:
    - `invTypes`: Contains item definitions (`typeID`, `typeName`, `groupID`, etc.).
    - `industryActivityProducts`: Contains manufacturing data linking blueprints/activities to products.
3.  **Libraries**: `pandas`, `sqlalchemy`.

## SQL Query Logic
The core logic relies on a `JOIN` between `invTypes` and `industryActivityProducts`.
- `industryActivityProducts.activityID = 1` corresponds to **Manufacturing**.
- The query selects distinct items that are products of a manufacturing activity.

```sql
SELECT DISTINCT t.typeID, t.typeName 
FROM invTypes t
JOIN industryActivityProducts iap ON t.typeID = iap.productTypeID
WHERE t.groupID = :group_id 
AND iap.activityID = 1
ORDER BY t.typeName
```

## Implementation

Here is the Python implementation using `pandas` and `sqlalchemy`:

```python
import pandas as pd
from sqlalchemy import text

def get_types_for_group(db_engine, group_id: int) -> pd.DataFrame:
    """
    Fetch buildable types for a specific group from the SDE database.
    
    Args:
        db_engine: SQLAlchemy engine connected to sdelite2.db
        group_id (int): The EVE Online group ID to filter by.
        
    Returns:
        pd.DataFrame: DataFrame with columns ['typeID', 'typeName']
    """
    query = """
        SELECT DISTINCT t.typeID, t.typeName 
        FROM invTypes t
        JOIN industryActivityProducts iap ON t.typeID = iap.productTypeID
        WHERE t.groupID = :group_id 
        AND iap.activityID = 1
        ORDER BY t.typeName
    """
    
    try:
        with db_engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params={"group_id": group_id})
    except Exception as e:
        print(f"Error fetching types for group {group_id}: {e}")
        # Return empty DataFrame with expected columns on error
        return pd.DataFrame(columns=['typeID', 'typeName'])

    # Special handling for "Tool" group (ID 332) to filter specific prefixes
    if group_id == 332:
        df = df[df['typeName'].str.contains("R.A.M.") | df['typeName'].str.contains("R.Db")]
        df = df.reset_index(drop=True)

    return df
```

## Migration Steps
1.  **Verify Database**: Ensure `sdelite2.db` is up to date and contains the `industryActivityProducts` table.
2.  **Update Function**: Replace the CSV-reading logic with the SQL query above.

