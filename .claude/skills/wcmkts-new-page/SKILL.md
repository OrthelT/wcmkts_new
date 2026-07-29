---
name: wcmkts-new-page
description: How to add a new Streamlit page to the Winter Coalition Market Stats Viewer - file naming, registration in app.py, and the service/repository factory pattern pages must use. Use when creating or registering a new page under pages/.
---

# Adding New Pages

1. Create new page file in `pages/` directory with emoji prefix (e.g., `📊_new_page.py`)
2. Add page registration in `app.py` pages dictionary
3. Use services and repositories via factory functions -- do not access `DatabaseConfig` directly
4. Use centralized logging from `logging_config.py`
5. Follow existing page patterns for consistency

Example:

```python
import streamlit as st
from services import get_market_service
from logging_config import setup_logging

logger = setup_logging("new_page")

def main():
    st.title("New Page")
    service = get_market_service()
    df = service.get_market_data(type_id)

if __name__ == "__main__":
    main()
```

Remember the layer rules from `AGENTS.md`: `pages/` may import from `state/`, `ui/`,
`services/`, `domain/`, and `repositories/` -- but reads go through repository/service
factories, never through a directly-constructed `DatabaseConfig`.
