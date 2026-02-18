"""Lightweight CLI for wcmkts database operations.

Usage:
    mkts sync              # sync both market databases (primary + deployment)
    mkts sync --primary    # sync primary market only (4-HWWF)
    mkts sync --deployment # sync deployment market only (B-9C24)
    mkts sync --north      # alias for --deployment
    mkts log-level DEBUG   # set log level in settings.toml
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from time import perf_counter

from settings_service import _load_settings

SETTINGS_PATH = Path("settings.toml")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _get_market_aliases(args: argparse.Namespace) -> list[str]:
    """Resolve CLI flags to database aliases using settings.toml."""
    settings = _load_settings()
    markets = settings["markets"]

    if args.primary:
        return [markets["primary"]["database_alias"]]
    if args.deployment or args.north:
        return [markets["deployment"]["database_alias"]]

    # No flag → both market databases
    return [m["database_alias"] for m in markets.values()]


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync one or more databases from Turso remote."""
    if not args.verbose:
        # Suppress library logs before config imports set up handlers
        logging.disable(logging.INFO)

    from config import DatabaseConfig

    aliases = _get_market_aliases(args)
    failed = []

    for alias in aliases:
        print(f"syncing {alias} …", end=" ", flush=True)
        t0 = perf_counter()
        try:
            db = DatabaseConfig(alias)
            ok = db.sync()
            elapsed = round((perf_counter() - t0) * 1000)
            if ok:
                print(f"ok ({elapsed} ms)")
            else:
                print(f"integrity check failed ({elapsed} ms)")
                failed.append(alias)
        except Exception as e:
            elapsed = round((perf_counter() - t0) * 1000)
            print(f"error ({elapsed} ms): {e}")
            failed.append(alias)

    if failed:
        print(f"\nfailed: {', '.join(failed)}")
        return 1
    return 0


def cmd_log_level(args: argparse.Namespace) -> int:
    """Get or set the log level in settings.toml."""
    settings = _load_settings()
    current = settings["env"]["log_level"]

    if args.level is None:
        print(current)
        return 0

    level = args.level.upper()
    if level not in VALID_LOG_LEVELS:
        print(f"invalid level: {args.level} (expected one of {', '.join(VALID_LOG_LEVELS)})")
        return 1

    if level == current:
        print(f"already {level}")
        return 0

    content = SETTINGS_PATH.read_text()
    updated = re.sub(
        r'(log_level\s*=\s*)"[^"]*"',
        rf'\1"{level}"',
        content,
    )
    SETTINGS_PATH.write_text(updated)
    print(f"{current} → {level}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="mkts", description="wcmkts CLI tools")
    sub = parser.add_subparsers(dest="command")

    sync_parser = sub.add_parser("sync", help="Sync databases from Turso remote")
    sync_parser.add_argument("--primary", action="store_true", help="Sync primary market (4-HWWF) only")
    sync_parser.add_argument("--deployment", action="store_true", help="Sync deployment market (B-9C24) only")
    sync_parser.add_argument("--north", action="store_true", help="Alias for --deployment")
    sync_parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed sync logs")

    ll_parser = sub.add_parser("log-level", help="Get or set the log level in settings.toml")
    ll_parser.add_argument("level", nargs="?", default=None, help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")

    args = parser.parse_args()

    if args.command == "sync":
        return cmd_sync(args)
    if args.command == "log-level":
        return cmd_log_level(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
