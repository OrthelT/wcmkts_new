"""Tests for the minutes_until_next_update helper in state.sync_state."""

from datetime import timedelta

import pytest

from state import sync_state


def _stub_session_state(monkeypatch, state):
    monkeypatch.setattr(sync_state.st, "session_state", state, raising=False)


class TestMinutesUntilNextUpdate:
    def test_returns_remaining_minutes_for_fresh_timestamp(self, monkeypatch):
        _stub_session_state(
            monkeypatch,
            {"local_update_status": {"time_since": timedelta(minutes=20)}},
        )
        assert sync_state.minutes_until_next_update() == 40

    def test_returns_zero_at_exact_boundary(self, monkeypatch):
        _stub_session_state(
            monkeypatch,
            {"local_update_status": {"time_since": timedelta(minutes=60)}},
        )
        assert sync_state.minutes_until_next_update() == 0

    def test_returns_zero_when_overdue_within_same_day(self, monkeypatch):
        _stub_session_state(
            monkeypatch,
            {"local_update_status": {"time_since": timedelta(minutes=75)}},
        )
        assert sync_state.minutes_until_next_update() == 0

    def test_returns_zero_for_multi_day_staleness(self, monkeypatch):
        # Regression guard: timedelta.seconds drops the days component, so
        # using `.seconds` here would have returned a misleading positive
        # countdown. .total_seconds() keeps the result honest.
        _stub_session_state(
            monkeypatch,
            {"local_update_status": {"time_since": timedelta(days=1, minutes=30)}},
        )
        assert sync_state.minutes_until_next_update() == 0

    def test_returns_full_interval_when_just_updated(self, monkeypatch):
        _stub_session_state(
            monkeypatch,
            {"local_update_status": {"time_since": timedelta(seconds=0)}},
        )
        assert sync_state.minutes_until_next_update() == 60

    def test_returns_none_when_status_missing_and_init_fails(self, monkeypatch):
        _stub_session_state(monkeypatch, {})

        def boom(*args, **kwargs):
            raise RuntimeError("db unreachable")

        monkeypatch.setattr(sync_state, "update_wcmkt_state", boom)
        assert sync_state.minutes_until_next_update() is None

    def test_returns_none_when_status_is_none(self, monkeypatch):
        _stub_session_state(monkeypatch, {"local_update_status": None})
        assert sync_state.minutes_until_next_update() is None

    def test_returns_none_when_time_since_is_none(self, monkeypatch):
        # This is the default shape populated by update_wcmkt_state() when
        # no local update has ever been recorded — must not crash callers.
        _stub_session_state(
            monkeypatch,
            {"local_update_status": {"updated": None, "time_since": None}},
        )
        assert sync_state.minutes_until_next_update() is None

    def test_calls_update_when_status_missing(self, monkeypatch):
        # Cold start: no local_update_status in session yet. The function
        # should call update_wcmkt_state() to populate it, then read.
        session = {}
        _stub_session_state(monkeypatch, session)

        def populate():
            session["local_update_status"] = {"time_since": timedelta(minutes=15)}

        monkeypatch.setattr(sync_state, "update_wcmkt_state", populate)
        assert sync_state.minutes_until_next_update() == 45


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
