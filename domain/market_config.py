"""
Market Configuration Domain Model

Pure Python dataclass representing a market hub's configuration.
No Streamlit or infrastructure dependencies — domain layer only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketConfig:
    """Immutable configuration for a single market hub.

    Attributes:
        key: Market identifier matching doctrine_fits.market_flag
             (e.g. "primary", "deployment")
        name: Full display name (e.g. "4-HWWF Keepstar")
        short_name: Abbreviated name for column headers (e.g. "4H")
        region_id: EVE region ID
        system_id: EVE solar system ID
        structure_id: EVE structure ID
        database_alias: Alias used by DatabaseConfig (e.g. "wcmktprod")
        database_file: Local database filename (e.g. "wcmktprod.db")
        turso_secret_key: Section name in secrets.toml for Turso creds
    """

    key: str
    name: str
    short_name: str
    region_id: int
    system_id: int
    structure_id: int
    database_alias: str
    database_file: str
    turso_secret_key: str


DEFAULT_MARKET_KEY = "primary"
