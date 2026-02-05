"""
Build Cost Service

Pure business logic for build cost calculations: URL construction, cost fetching
(sync/async), industry index management. No Streamlit imports.

Design Principles:
1. Dependency Injection - BuildCostRepository passed in, not created
2. Pure Functions - No session state, no UI, no caching (caching is in repo layer)
3. Testable - Progress callbacks are protocol-based, not Streamlit-specific
4. BuildCostJob dataclass replaces page-level JobQuery
"""

import asyncio
import datetime
from dataclasses import dataclass
from typing import Protocol, Optional

import httpx
import pandas as pd
import requests

from logging_config import setup_logging

logger = setup_logging(__name__, log_file="build_cost_service.log")


# =============================================================================
# Constants
# =============================================================================

PRICE_SOURCE_MAP = {
    "ESI Average": "ESI_AVG",
    "Jita Sell": "FUZZWORK_JITA_SELL_MIN",
    "Jita Buy": "FUZZWORK_JITA_BUY_MAX",
}

SUPER_GROUP_IDS = [30, 659]

API_TIMEOUT = 20.0
MAX_CONCURRENCY = 6
RETRIES = 2
USER_AGENT = (
    "WCMKTS-BuildCosts/1.0 "
    "(https://github.com/OrthelT/wcmkts_production; orthel.toralen@gmail.com)"
)
ESI_USER_AGENT = (
    "WC Markets v0.52 "
    "(admin contact: Orthel.Toralen@gmail.com; "
    "+https://github.com/OrthelT/wcmkts_new"
)


# =============================================================================
# Protocol
# =============================================================================

class ProgressCallback(Protocol):
    def __call__(self, current: int, total: int, message: str) -> None: ...


def _noop_progress(current: int, total: int, message: str) -> None:
    """Default no-op progress callback."""
    pass


# =============================================================================
# Domain Model
# =============================================================================

@dataclass
class BuildCostJob:
    """Parameters for a build cost calculation job."""
    item: str
    item_id: int
    group_id: int
    runs: int
    me: int
    te: int
    security: str = "NULL_SEC"
    system_cost_bonus: float = 0.0
    material_prices: str = "ESI_AVG"

    @property
    def is_super(self) -> bool:
        return self.group_id in SUPER_GROUP_IDS


# =============================================================================
# Build Cost Service
# =============================================================================

class BuildCostService:
    """Service for build cost calculations.

    Args:
        repo: BuildCostRepository instance for data access.
    """

    def __init__(self, repo):
        self._repo = repo

    # -----------------------------------------------------------------
    # URL Construction
    # -----------------------------------------------------------------

    def build_urls(self, job: BuildCostJob) -> list[tuple[str, str, str]]:
        """Build API URLs for all structures.

        Returns:
            List of (url, structure_name, structure_type) tuples.
        """
        structures = self._repo.get_all_structures(is_super=job.is_super)
        valid_rigs = self._repo.get_valid_rigs()
        urls = []

        for structure in structures:
            url = self._construct_url(job, structure, valid_rigs)
            urls.append((url, structure.structure, structure.structure_type))

        return urls

    def _construct_url(self, job: BuildCostJob, structure, valid_rigs: dict[str, int]) -> str:
        """Construct a single EverRef API URL for a structure."""
        rigs = [structure.rig_1, structure.rig_2, structure.rig_3]
        clean_rigs = [rig for rig in rigs if rig != "0" and rig is not None]
        clean_rigs = [rig for rig in clean_rigs if rig in valid_rigs]
        clean_rig_ids = [valid_rigs[rig] for rig in clean_rigs]

        system_cost_index = self._repo.get_manufacturing_cost_index(structure.system_id)
        tax = structure.tax

        formatted_rigs = "".join(f"&rig_id={rig_id}" for rig_id in clean_rig_ids)
        url = (
            f"https://api.everef.net/v1/industry/cost?"
            f"product_id={job.item_id}&runs={job.runs}&me={job.me}&te={job.te}"
            f"&structure_type_id={structure.structure_type_id}"
            f"&security={job.security}{formatted_rigs}"
            f"&system_cost_bonus={job.system_cost_bonus}"
            f"&manufacturing_cost={system_cost_index}"
            f"&facility_tax={tax}"
            f"&material_prices={job.material_prices}"
        )
        return url

    # -----------------------------------------------------------------
    # Cost Fetching
    # -----------------------------------------------------------------

    def get_costs(
        self,
        job: BuildCostJob,
        async_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> tuple[dict, dict]:
        """Fetch build costs from the EverRef API.

        Args:
            job: Build cost job parameters.
            async_mode: Use async HTTP client if True.
            progress_callback: Optional callback(current, total, message).

        Returns:
            (results_dict, status_log) tuple.
        """
        cb = progress_callback or _noop_progress

        if async_mode:
            return asyncio.run(self._get_costs_async(job, cb))
        else:
            return self._get_costs_sync(job, cb)

    def _get_costs_sync(
        self, job: BuildCostJob, progress_callback: ProgressCallback
    ) -> tuple[dict, dict]:
        """Synchronous cost fetching."""
        urls = self.build_urls(job)
        status_log = {
            "req_count": 0,
            "success_count": 0,
            "error_count": 0,
            "success_log": {},
            "error_log": {},
        }
        results = {}
        total = len(urls)

        progress_callback(0, total, f"Fetching data from {total} structures...")

        for i, (url, structure_name, structure_type) in enumerate(urls):
            logger.info(structure_name)
            status = f"Fetching {i + 1} of {total} structures: {structure_name}"
            progress_callback(i, total, status)

            response = requests.get(url, timeout=API_TIMEOUT)
            status_log["req_count"] += 1

            if response.status_code == 200:
                status_log["success_count"] += 1
                status_log["success_log"][structure_name] = (
                    response.status_code,
                    response.text,
                )
                data = response.json()
                try:
                    data2 = data["manufacturing"][str(job.item_id)]
                except KeyError as e:
                    logger.error(f"No data found for {job.item_id}: {e}")
                    return {}, status_log
            else:
                status_log["error_count"] += 1
                status_log["error_log"][structure_name] = (
                    response.status_code,
                    response.text,
                )
                logger.error(
                    f"Error fetching data for {structure_name}: {response.status_code}"
                )
                continue

            results[structure_name] = self._parse_cost_result(
                data2, structure_type
            )

        return results, status_log

    async def _get_costs_async(
        self, job: BuildCostJob, progress_callback: ProgressCallback
    ) -> tuple[dict, dict]:
        """Asynchronous cost fetching."""
        urls = self.build_urls(job)
        status_log = {
            "req_count": 0,
            "success_count": 0,
            "error_count": 0,
            "success_log": {},
            "error_log": {},
        }
        results = {}
        total = len(urls)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        limits = httpx.Limits(
            max_connections=MAX_CONCURRENCY,
            max_keepalive_connections=MAX_CONCURRENCY,
        )
        headers = {"User-Agent": USER_AGENT}

        async def fetch_with_semaphore(client, url, sname, stype):
            async with semaphore:
                return await self._fetch_one(client, url, sname, stype, job)

        progress_callback(0, total, f"Fetching data from {total} structures...")

        async with httpx.AsyncClient(
            http2=True, limits=limits, headers=headers
        ) as client:
            tasks = [
                fetch_with_semaphore(client, url, sname, stype)
                for url, sname, stype in urls
            ]

            for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
                structure_name, result, error = await coro
                status = f"Fetching {i} of {total} structures: {structure_name}"
                progress_callback(i, total, status)
                status_log["req_count"] += 1

                if result:
                    results[structure_name] = result
                    status_log["success_count"] += 1
                    status_log["success_log"][structure_name] = (result, None)
                if error:
                    status_log["error_count"] += 1
                    status_log["error_log"][structure_name] = (None, error)

        if status_log["error_count"] > 0:
            for s, e in status_log["error_log"].items():
                logger.error(f"Error fetching {s}: {e}")

        logger.info("=" * 80)
        logger.info(f"Results of {total} structures:")
        logger.info(f"Results count: {status_log['success_count']}")
        logger.info(f"Errors count: {status_log['error_count']}")
        logger.info("=" * 80)

        return results, status_log

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        url: str,
        structure_name: str,
        structure_type: str,
        job: BuildCostJob,
    ) -> tuple[str, dict | None, str | None]:
        """Fetch a single structure's cost data."""
        try:
            r = await client.get(url, timeout=API_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            try:
                data2 = data["manufacturing"][str(job.item_id)]
            except KeyError:
                return structure_name, None, f"No data found for {job.item_id}"
            return structure_name, self._parse_cost_result(data2, structure_type), None
        except Exception as e:
            return structure_name, None, str(e)

    @staticmethod
    def _parse_cost_result(data2: dict, structure_type: str) -> dict:
        """Parse API response into a cost result dict."""
        return {
            "structure_type": structure_type,
            "units": data2["units"],
            "total_cost": data2["total_cost"],
            "total_cost_per_unit": data2["total_cost_per_unit"],
            "total_material_cost": data2["total_material_cost"],
            "facility_tax": data2["facility_tax"],
            "scc_surcharge": data2["scc_surcharge"],
            "system_cost_index": data2["system_cost_index"],
            "total_job_cost": data2["total_job_cost"],
            "materials": data2["materials"],
        }

    # -----------------------------------------------------------------
    # Industry Index Management
    # -----------------------------------------------------------------

    def check_and_update_industry_index(
        self,
        expires: Optional[datetime.datetime],
        etag: Optional[str],
    ) -> tuple[
        Optional[datetime.datetime],
        Optional[datetime.datetime],
        Optional[str],
    ]:
        """Check if the industry index needs updating and refresh if expired.

        Args:
            expires: Current expiry timestamp (None = never fetched).
            etag: Current ETag for conditional request.

        Returns:
            (last_modified, expires, etag) if updated, or (None, None, None) if current.
        """
        now = datetime.datetime.now().astimezone(datetime.UTC)
        if expires is not None and expires >= now:
            logger.info("Industry index still current, skipping update")
            return None, None, None

        logger.info("Industry index expired or missing, updating")
        return self._fetch_and_store_industry_index(etag)

    def _fetch_and_store_industry_index(
        self, etag: Optional[str]
    ) -> tuple[
        Optional[datetime.datetime],
        Optional[datetime.datetime],
        Optional[str],
    ]:
        """Fetch industry indices from ESI and store in DB.

        Returns:
            (last_modified, expires, new_etag) if updated, (None, None, None) if 304.
        """
        url = "https://esi.evetech.net/latest/industry/systems/?datasource=tranquility"

        headers = {
            "Accept": "application/json",
            "User-Agent": ESI_USER_AGENT,
        }
        if etag:
            headers["If-None-Match"] = etag

        response = requests.get(url, headers=headers)
        logger.debug(f"ESI status: {response.status_code}")

        new_etag = response.headers.get("ETag")

        if response.status_code == 304:
            logger.info("Industry index current (304)")
            return None, None, None

        elif response.status_code == 200:
            systems_data = response.json()
            last_modified = datetime.datetime.strptime(
                response.headers.get("Last-Modified"),
                "%a, %d %b %Y %H:%M:%S GMT",
            ).replace(tzinfo=datetime.timezone.utc)
            new_expires = datetime.datetime.strptime(
                response.headers.get("Expires"),
                "%a, %d %b %Y %H:%M:%S GMT",
            ).replace(tzinfo=datetime.timezone.utc)

            logger.info(f"SCI last modified: {last_modified}")
            logger.info(f"SCI expires: {new_expires}")

            df = self._parse_industry_data(systems_data)
            self._repo.write_industry_index(df)

            current_time = datetime.datetime.now().astimezone(datetime.UTC)
            logger.info(f"Industry index updated at {current_time}")

            return last_modified, new_expires, new_etag
        else:
            response.raise_for_status()
            return None, None, None  # unreachable, but satisfies type checker

    @staticmethod
    def _parse_industry_data(systems_data: list[dict]) -> pd.DataFrame:
        """Parse ESI industry systems response into a DataFrame."""
        flat_records = []
        for system in systems_data:
            system_id = system["solar_system_id"]
            for activity_info in system["cost_indices"]:
                flat_records.append({
                    "system_id": system_id,
                    "activity": activity_info["activity"],
                    "cost_index": activity_info["cost_index"],
                })

        df = pd.DataFrame(flat_records)
        df = df.pivot(index="system_id", columns="activity", values="cost_index")
        df.reset_index(inplace=True)
        df.rename(columns={"system_id": "solar_system_id"}, inplace=True)
        return df

    # -----------------------------------------------------------------
    # Static Utilities
    # -----------------------------------------------------------------

    @staticmethod
    def get_type_id(type_name: str) -> int:
        """Look up a type_id by name using the Fuzzwork API."""
        url = f"https://www.fuzzwork.co.uk/api/typeid.php?typename={type_name}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return int(data["typeID"])
        else:
            logger.error(f"Error fetching type id: {response.status_code}")
            raise ValueError(
                f"Error fetching type id for {type_name}: {response.status_code}"
            )

    @staticmethod
    def is_super_group(group_id: int) -> bool:
        """Check if a group_id is a supercapital group."""
        return group_id in SUPER_GROUP_IDS


# =============================================================================
# Factory Function
# =============================================================================

def get_build_cost_service() -> BuildCostService:
    """Get or create a BuildCostService instance.

    Uses state.get_service for session persistence. Falls back to
    direct instantiation if state module is unavailable.
    """
    def _create() -> BuildCostService:
        from repositories.build_cost_repo import get_build_cost_repository
        repo = get_build_cost_repository()
        return BuildCostService(repo)

    try:
        from state import get_service
        return get_service("build_cost_service", _create)
    except ImportError:
        return _create()
