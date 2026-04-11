"""Tests for db update schedule helpers in settings_service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from settings_service import (
    get_db_update_schedule,
    minutes_until_next_db_update,
    time_until_next_db_update,
)


def _fake_settings(frequency: int, minute: int) -> dict:
    return {"db_update": {"frequency": frequency, "time": minute}}


class TestGetDbUpdateSchedule:
    def test_reads_values_from_settings(self):
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(2, 15)
        ):
            assert get_db_update_schedule() == (2, 15)

    def test_defaults_when_section_missing(self):
        with patch("settings_service._load_settings", return_value={}):
            assert get_db_update_schedule() == (1, 0)

    def test_clamps_invalid_values(self):
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(0, 75)
        ):
            freq, minute = get_db_update_schedule()
            assert freq == 1
            assert minute == 59


class TestTimeUntilNextDbUpdate:
    def test_hourly_before_slot(self):
        now = datetime(2026, 4, 10, 14, 15, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            delta = time_until_next_db_update(now)
            assert delta == timedelta(minutes=5)

    def test_hourly_after_slot_rolls_to_next_hour(self):
        now = datetime(2026, 4, 10, 14, 25, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            delta = time_until_next_db_update(now)
            assert delta == timedelta(minutes=55)

    def test_every_two_hours_midnight_anchored(self):
        # Slots at 00:20, 02:20, 04:20, ... — now is 05:00, next is 06:20
        now = datetime(2026, 4, 10, 5, 0, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(2, 20)
        ):
            delta = time_until_next_db_update(now)
            assert delta == timedelta(hours=1, minutes=20)

    def test_rolls_to_next_day_when_past_last_slot(self):
        # Hourly :20 — now is 23:45, next is tomorrow 00:20
        now = datetime(2026, 4, 10, 23, 45, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            delta = time_until_next_db_update(now)
            assert delta == timedelta(minutes=35)

    def test_naive_datetime_treated_as_utc(self):
        now = datetime(2026, 4, 10, 14, 15)  # naive
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            delta = time_until_next_db_update(now)
            assert delta == timedelta(minutes=5)


class TestMinutesUntilNextDbUpdate:
    def test_rounds_up_to_whole_minute(self):
        now = datetime(2026, 4, 10, 14, 19, 30, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            # 30 seconds → 1 minute (rounded up, never reports 0)
            assert minutes_until_next_db_update(now) == 1

    def test_never_returns_zero(self):
        now = datetime(2026, 4, 10, 14, 19, 59, 999999, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            assert minutes_until_next_db_update(now) >= 1

    def test_matches_time_until(self):
        now = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
        with patch(
            "settings_service._load_settings", return_value=_fake_settings(1, 20)
        ):
            assert minutes_until_next_db_update(now) == 20
