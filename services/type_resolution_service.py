"""
Type Resolution Service

Resolves EVE Online type names to IDs (and vice versa) using SDE database
lookups with external API fallbacks.

Absorbs functions from:
- type_info.py: get_type_id_with_fallback(), get_type_id_from_fuzzworks()
- db_handler.py: request_type_names() (ESI batch API)

Design:
- Receives SDERepository via DI for database lookups
- Fuzzworks API fallback for type ID resolution
- ESI batch API for type name resolution
- No Streamlit imports (service layer rule)
"""

import logging
from typing import Optional

import requests

from logging_config import setup_logging
from repositories.sde_repo import SDERepository

logger = setup_logging(__name__, log_file="type_resolution_service.log")


class TypeResolutionService:
    """Resolves type names <-> IDs using SDE with API fallbacks."""

    def __init__(self, sde_repo: SDERepository):
        self._sde_repo = sde_repo

    def resolve_type_id(self, type_name: str) -> Optional[int]:
        """Resolve a type name to its type ID.

        Tries SDE database first, falls back to Fuzzworks API.
        Returns None if both lookups fail.
        """
        type_id = self._sde_repo.get_type_id(type_name)
        if type_id is not None:
            logger.debug(f"SDE found type_id for {type_name}: {type_id}")
            return type_id

        type_id = self._fetch_type_id_from_fuzzworks(type_name)
        if type_id is not None:
            logger.debug(f"Fuzzworks found type_id for {type_name}: {type_id}")
            return type_id

        logger.error(f"No type_id found for {type_name}")
        return None

    def resolve_type_names(self, type_ids: list[int]) -> list[dict]:
        """Resolve multiple type IDs to names via ESI batch API.

        Processes in chunks of 1000 (ESI limit).
        Returns list of dicts with 'id', 'name', 'category' keys.
        """
        return self._fetch_type_names_from_esi(type_ids)

    @staticmethod
    def _fetch_type_id_from_fuzzworks(type_name: str) -> Optional[int]:
        """Look up a type ID from the Fuzzworks API."""
        try:
            url = f"https://www.fuzzwork.co.uk/api/typeid.php?typename={type_name}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return int(data["typeID"])
            else:
                logger.error(f"Fuzzworks API error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching type_id from Fuzzworks for {type_name}: {e}")
            return None

    @staticmethod
    def _fetch_type_names_from_esi(type_ids: list[int]) -> list[dict]:
        """Batch fetch type names from the ESI universe/names endpoint.

        Processes in chunks of 1000 to stay within ESI limits.
        """
        chunk_size = 1000
        all_results = []

        for i in range(0, len(type_ids), chunk_size):
            chunk = type_ids[i : i + chunk_size]
            url = "https://esi.evetech.net/latest/universe/names/?datasource=tranquility"
            headers = {
                "Accept": "application/json",
                "User-Agent": "dfexplorer",
            }
            try:
                response = requests.post(url, headers=headers, json=chunk, timeout=30)
                if response.status_code == 200:
                    all_results.extend(response.json())
                else:
                    logger.error(f"ESI names API error: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching type names from ESI: {e}")

        return all_results


# =============================================================================
# Factory Function
# =============================================================================

def get_type_resolution_service() -> TypeResolutionService:
    """Get or create a TypeResolutionService instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.
    """
    def _create() -> TypeResolutionService:
        from repositories.sde_repo import get_sde_repository
        sde_repo = get_sde_repository()
        return TypeResolutionService(sde_repo)

    try:
        from state import get_service
        return get_service("type_resolution_service", _create)
    except ImportError:
        logger.debug("state module unavailable, creating new TypeResolutionService")
        return _create()
