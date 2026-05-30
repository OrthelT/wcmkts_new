"""pyturso pull/push adapter — demonstrates the planned libsql → pyturso move.

Your current data layer (config.py) uses `libsql` embedded replicas with a
single `conn.sync()`. pyturso (the successor) changes two things that matter
for an interactive app:

  1. Local writes are first-class (MVCC, full concurrency) — so per-user state
     (favorites, notes, cached ESI pulls) can live in the SAME local DB.
  2. The sync API splits: `sync()` becomes `pull()` (remote → local) and a new
     `push()` (local → remote) is added.

This adapter is written defensively: if `turso` (pyturso) isn't installed yet,
it transparently falls back to stdlib sqlite3 so the POC still runs. The public
method names (`pull`, `push`) match the target API so the migration shape is
visible.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger("poc.turso")

_DB_PATH = Path(__file__).resolve().parent / "poc_local.db"


class TursoLikeAdapter:
    """Minimal data layer modeling the pyturso pull/push contract.

    Compare with config.py today:

        # --- libsql (current) ---
        conn = libsql.connect(path, sync_url=url, auth_token=token)
        conn.sync()                      # remote -> local only

        # --- pyturso (target) ---
        conn = turso.connect(path, sync_url=url, auth_token=token)
        conn.pull()                      # remote -> local
        conn.push()                      # local  -> remote   (NEW)
    """

    def __init__(self) -> None:
        self._backend = "sqlite3 (fallback)"
        self._conn = None
        self._sync_url = os.getenv("TURSO_SYNC_URL")
        self._auth_token = os.getenv("TURSO_AUTH_TOKEN")
        self._connect()
        self._ensure_schema()

    # -- connection -------------------------------------------------------
    def _connect(self) -> None:
        try:
            import turso  # pyturso

            if self._sync_url and self._auth_token:
                self._conn = turso.connect(
                    str(_DB_PATH),
                    sync_url=self._sync_url,
                    auth_token=self._auth_token,
                )
            else:
                self._conn = turso.connect(str(_DB_PATH))
            self._backend = "pyturso"
        except Exception as exc:  # noqa: BLE001 - POC: degrade to stdlib
            logger.info("pyturso unavailable (%s); using sqlite3 fallback.", exc)
            self._conn = sqlite3.connect(
                str(_DB_PATH), check_same_thread=False, timeout=30
            )
            self._conn.execute("PRAGMA journal_mode=WAL")

    def _ensure_schema(self) -> None:
        # A local-write table — the capability libsql replicas lacked.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS user_favorites ("
            "character_id INTEGER NOT NULL,"
            "fit_id INTEGER NOT NULL,"
            "PRIMARY KEY (character_id, fit_id))"
        )
        self._conn.commit()

    @property
    def backend(self) -> str:
        return self._backend

    # -- the pull/push contract ------------------------------------------
    def pull(self) -> bool:
        """Remote -> local (replaces libsql `sync()`)."""
        pull = getattr(self._conn, "pull", None)
        if callable(pull):
            pull()
            logger.info("pyturso pull() complete")
            return True
        logger.info("pull() is a no-op on the sqlite3 fallback")
        return False

    def push(self) -> bool:
        """Local -> remote (NEW in pyturso; impossible with libsql replicas)."""
        push = getattr(self._conn, "push", None)
        if callable(push):
            push()
            logger.info("pyturso push() complete")
            return True
        logger.info("push() is a no-op on the sqlite3 fallback")
        return False

    # -- local writes (the headline pyturso capability) -------------------
    def toggle_favorite(self, character_id: int, fit_id: int) -> bool:
        """Add/remove a favorite locally, then push upstream. Returns new state."""
        cur = self._conn.execute(
            "SELECT 1 FROM user_favorites WHERE character_id=? AND fit_id=?",
            (character_id, fit_id),
        )
        exists = cur.fetchone() is not None
        if exists:
            self._conn.execute(
                "DELETE FROM user_favorites WHERE character_id=? AND fit_id=?",
                (character_id, fit_id),
            )
            new_state = False
        else:
            self._conn.execute(
                "INSERT INTO user_favorites (character_id, fit_id) VALUES (?, ?)",
                (character_id, fit_id),
            )
            new_state = True
        self._conn.commit()
        self.push()  # write-through to remote — the new capability
        return new_state

    def get_favorites(self, character_id: int) -> set[int]:
        cur = self._conn.execute(
            "SELECT fit_id FROM user_favorites WHERE character_id=?", (character_id,)
        )
        return {row[0] for row in cur.fetchall()}
