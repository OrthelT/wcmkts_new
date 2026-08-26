"""Shape inspection for the pyturso ``-info`` replica-metadata sidecar.

pyturso writes ``<database>-info`` beside every synced replica. A libsql-era
``-info`` is *valid JSON*, so checking existence (or merely parsing it) accepts
a file that pyturso cannot use: the first engine call then raises
``turso.lib.DatabaseError`` with nothing pointing at the metadata.

The two discriminators are stable across pyturso 0.7.x: ``version`` is the
string ``"v1"`` (libsql wrote an integer ``0``) and ``client_unique_id`` is a
non-empty string that libsql never wrote.

This module reads one file and returns plain data. It deliberately imports
nothing from ``db_config`` so it stays cheap to test and simple to port to the
frontend, which has no shared package with this repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

METADATA_SUFFIX = "-info"

MetadataKind = Literal["pyturso", "libsql", "corrupt", "missing"]


def metadata_path(db_path: str | Path) -> Path:
    """The ``-info`` sidecar beside ``db_path``."""
    return Path(f"{db_path}{METADATA_SUFFIX}")


def _load(db_path: str | Path) -> dict | None:
    """Parsed metadata mapping, or None if absent, unreadable or not a mapping."""
    info = metadata_path(db_path)
    if not info.exists():
        return None
    try:
        payload = json.loads(info.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def classify_metadata(db_path: str | Path) -> MetadataKind:
    """Classify the ``-info`` sidecar beside ``db_path``.

    Returns:
        "pyturso" — usable pyturso metadata.
        "libsql"  — libsql-era metadata; the replica must be re-pulled.
        "corrupt" — present but unparseable or of an unrecognised shape.
        "missing" — no ``-info`` file.
    """
    if not metadata_path(db_path).exists():
        return "missing"
    meta = _load(db_path)
    if meta is None:
        return "corrupt"
    version = meta.get("version")
    client_unique_id = meta.get("client_unique_id")
    if (
        version == "v1"
        and isinstance(client_unique_id, str)
        and bool(client_unique_id.strip())
    ):
        return "pyturso"
    if "hash" in meta and isinstance(version, int):
        return "libsql"
    return "corrupt"


def metadata_remote_url(db_path: str | Path) -> str | None:
    """The remote this replica was bootstrapped against, or None.

    pyturso records the bootstrap remote in
    ``saved_configuration.remote_url``. Comparing it against the configured
    URL catches a test replica left in place under a production configuration
    without printing any token.
    """
    if classify_metadata(db_path) != "pyturso":
        return None
    meta = _load(db_path) or {}
    saved = meta.get("saved_configuration")
    if not isinstance(saved, dict):
        return None
    url = saved.get("remote_url")
    return url if isinstance(url, str) and url else None
