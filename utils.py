import streamlit as st
from logging_config import setup_logging
import requests
from config import DatabaseConfig

# ============================================================================
# Session State Utilities (DEPRECATED - use state/ module directly)
# ============================================================================
# These re-exports maintain backward compatibility.
# New code should import from state/ module:
#   from state import ss_get, ss_has, ss_init
from state.session_state import ss_get, ss_has, ss_init

mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")

logger = setup_logging(__name__)

@st.cache_data(ttl=600)
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
        return None

def get_janice_price(type_id: int) -> float:
    api_key = st.secrets.janice.api_key
    url = f"https://janice.e-351.com/api/rest/v2/pricer/{type_id}?market=2"

    headers = {'X-ApiKey': api_key, 'accept': 'application/json'}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        return data.get("top5AveragePrices").get("sellPrice")
    else:
        logger.error(f"Error fetching price for {type_id}: {response.status_code}")
        return None

@st.cache_data(ttl=3600)
def get_multi_item_jita_price(type_ids: list[int]) -> dict[int, float]:
    """
    Fetch Jita prices for multiple items at once using Fuzzwork API.
    
    Args:
        type_ids: List of EVE Online type IDs to fetch prices for
    
    Returns:
        dict: Mapping of type_id -> price (sell percentile price)
              Returns empty dict on error
    """
    if not type_ids:
        return {}
    
    try:
        # Convert type_ids to comma-separated string
        type_ids_str = ','.join(map(str, type_ids))
        url = f"https://market.fuzzwork.co.uk/aggregates/?region=10000002&types={type_ids_str}"
        
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            # Parse response and extract sell percentile prices
            prices = {}
            for type_id in type_ids:
                type_id_str = str(type_id)
                if type_id_str in data and 'sell' in data[type_id_str]:
                    # Get percentile price (similar to single item function)
                    price = data[type_id_str]['sell'].get('percentile')
                    if price is not None:
                        prices[type_id] = float(price)
                    else:
                        logger.warning(f"No percentile price found for type_id {type_id}")
                else:
                    logger.warning(f"No sell data found for type_id {type_id}")
            
            return prices
        else:
            logger.error(f"Error fetching batch prices from Fuzzwork: {response.status_code}")
            # Fall back to Janice API
            return get_multi_item_janice_price(type_ids)
    except requests.exceptions.ReadTimeout:
        logger.error("Timeout fetching batch prices from Fuzzwork")
        return get_multi_item_janice_price(type_ids)
    except Exception as e:
        logger.error(f"Error fetching batch prices from Fuzzwork: {e}")
        return get_multi_item_janice_price(type_ids)

def get_multi_item_janice_price(type_ids: list[int]) -> dict[int, float]:
    """
    Fetch Jita prices for multiple items at once using Janice API as fallback.
    
    Args:
        type_ids: List of EVE Online type IDs to fetch prices for
    
    Returns:
        dict: Mapping of type_id -> price (sell price)
              Returns empty dict on error
    """
    if not type_ids:
        return {}
    
    try:
        api_key = st.secrets.janice.api_key
        url = "https://janice.e-351.com/api/rest/v2/pricer"
        
        # Janice expects type_ids as newline-separated string in POST body
        body = '\n'.join(map(str, type_ids))
        
        headers = {
            'X-ApiKey': api_key,
            'accept': 'application/json',
            'Content-Type': 'text/plain'
        }
        
        # Market 2 is Jita
        params = {'market': '2'}
        
        response = requests.post(url, data=body, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse Janice response
            prices = {}
            if 'appraisalItems' in data:
                for item in data['appraisalItems']:
                    type_id = item.get('typeID')
                    if type_id and 'prices' in item:
                        # Get sell price from top5AveragePrices
                        sell_price = item['prices'].get('top5AveragePrices', {}).get('sellPrice')
                        if sell_price is not None:
                            prices[type_id] = float(sell_price)
                        else:
                            logger.warning(f"No sell price found for type_id {type_id} in Janice response")
            
            return prices
        else:
            logger.error(f"Error fetching batch prices from Janice: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching batch prices from Janice: {e}")
        return {}

if __name__ == "__main__":
    pass
