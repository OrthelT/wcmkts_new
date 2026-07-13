"""SyncResult: sync() return type preserving `if db.sync():` truthiness."""

import dataclasses

import pytest

from config import SyncResult


def test_truthiness_follows_ok():
    assert SyncResult(ok=True, changed=False)
    assert SyncResult(ok=True, changed=True)
    assert not SyncResult(ok=False, changed=False)
    assert not SyncResult(ok=False, changed=True)


def test_fields():
    r = SyncResult(ok=True, changed=True)
    assert r.ok is True
    assert r.changed is True


def test_frozen():
    r = SyncResult(ok=True, changed=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.ok = False
