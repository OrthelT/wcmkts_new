"""Tests for admin page helpers."""

import pandas as pd
import pytest

from pages import admin as admin_page
from pages.admin import (
    NOTICE_KEY,
    PENDING_ADDS_KEY,
    PENDING_REMOVES_KEY,
    _commit_save,
    summarize_watchlist_changes,
)


def test_summarize_watchlist_changes_counts_add_update_remove():
    original = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
            {
                "type_id": 35,
                "group_id": 18,
                "type_name": "Pyerite",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
        ]
    )
    edited = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Raw Material",
            },
            {
                "type_id": 36,
                "group_id": 18,
                "type_name": "Mexallon",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
        ]
    )

    summary = summarize_watchlist_changes(original, edited)

    assert summary == {"added": 1, "changed": 1, "removed": 1}


# ---- _commit_save -----------------------------------------------------------


class _RerunCalled(BaseException):
    """Sentinel raised in place of st.rerun() to interrupt execution in tests.

    Inherits from BaseException (not Exception) to mirror Streamlit's real
    RerunException, which uses BaseException so user code's `except Exception`
    blocks don't accidentally suppress the rerun signal.
    """


class _StubService:
    def __init__(self, *, raises=None, result=None):
        self._raises = raises
        self._result = result or {"row_count": 1, "added_type_ids": [], "removed_type_ids": []}
        self.calls = []

    def save_watchlist(self, df, *, signed_identity):
        self.calls.append({"df": df, "signed_identity": signed_identity})
        if self._raises is not None:
            raise self._raises
        return self._result


@pytest.fixture
def streamlit_doubles(monkeypatch):
    """Replace pages.admin.st.{error,session_state,rerun} with test doubles."""
    session_state = {
        PENDING_ADDS_KEY: [{"type_id": 34}],
        PENDING_REMOVES_KEY: [35],
    }
    errors: list[str] = []

    def _rerun():
        raise _RerunCalled()

    monkeypatch.setattr(admin_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(admin_page.st, "error", lambda msg: errors.append(msg))
    monkeypatch.setattr(admin_page.st, "rerun", _rerun)
    return session_state, errors


def test_commit_save_refuses_empty_dataframe(streamlit_doubles):
    session_state, errors = streamlit_doubles
    service = _StubService()

    _commit_save(service, {"new_df": pd.DataFrame()}, signed_identity=None)

    assert errors == ["Refusing to save an empty watchlist."]
    assert service.calls == []
    assert session_state[PENDING_ADDS_KEY] == [{"type_id": 34}]
    assert session_state[PENDING_REMOVES_KEY] == [35]


def test_commit_save_success_clears_pending_queues_and_sets_notice(streamlit_doubles):
    session_state, errors = streamlit_doubles
    service = _StubService(
        result={"row_count": 2, "added_type_ids": [99], "removed_type_ids": [42]}
    )
    new_df = pd.DataFrame(
        [
            {
                "type_id": 99,
                "group_id": 1,
                "type_name": "X",
                "group_name": "Y",
                "category_id": 1,
                "category_name": "Z",
            }
        ]
    )

    with pytest.raises(_RerunCalled):
        _commit_save(service, {"new_df": new_df}, signed_identity={"signature": "s"})

    assert errors == []
    assert session_state[PENDING_ADDS_KEY] == []
    assert session_state[PENDING_REMOVES_KEY] == []
    assert "Saved 2 watchlist rows" in session_state[NOTICE_KEY]
    assert "[99]" in session_state[NOTICE_KEY]
    assert "[42]" in session_state[NOTICE_KEY]
    assert len(service.calls) == 1


def test_commit_save_surfaces_value_error_verbatim_and_keeps_queues(streamlit_doubles):
    session_state, errors = streamlit_doubles
    service = _StubService(raises=ValueError("type_id must be an integer"))

    _commit_save(
        service,
        {"new_df": pd.DataFrame([{"type_id": 1}])},
        signed_identity=None,
    )

    assert errors == ["type_id must be an integer"]
    assert session_state[PENDING_ADDS_KEY] == [{"type_id": 34}]
    assert session_state[PENDING_REMOVES_KEY] == [35]


def test_commit_save_translates_permission_error_to_friendly_message(streamlit_doubles):
    session_state, errors = streamlit_doubles
    service = _StubService(raises=PermissionError("Admin authentication required"))

    _commit_save(
        service,
        {"new_df": pd.DataFrame([{"type_id": 1}])},
        signed_identity=None,
    )

    assert errors == ["Admin session expired or unauthorized. Please log in again."]
    assert "Admin authentication required" not in errors[0]
    assert session_state[PENDING_ADDS_KEY] == [{"type_id": 34}]
    assert session_state[PENDING_REMOVES_KEY] == [35]


def test_commit_save_translates_unexpected_exception_to_friendly_message(streamlit_doubles):
    session_state, errors = streamlit_doubles
    service = _StubService(raises=RuntimeError("turso connection dropped"))

    _commit_save(
        service,
        {"new_df": pd.DataFrame([{"type_id": 1}])},
        signed_identity=None,
    )

    assert errors == ["Failed to save watchlist. Check admin logs for details."]
    assert "turso" not in errors[0]
    assert session_state[PENDING_ADDS_KEY] == [{"type_id": 34}]
    assert session_state[PENDING_REMOVES_KEY] == [35]
