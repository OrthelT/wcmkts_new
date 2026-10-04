"""Tests for build_doctrine_usage (the market popover "Used In Fits" data)."""

import pandas as pd

from services.doctrine_service import build_doctrine_usage


def _raw_df(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["fit_id", "type_id", "ship_name", "fit_qty", "fits_on_mkt", "price"]
    )


def test_groups_fits_by_type_id():
    raw = _raw_df([
        (1, 100, "Ferox", 2, 5, 10.0),
        (2, 100, "Drake", 3, 4, 10.0),
        (2, 200, "Drake", 1, 9, 20.0),
    ])

    usage = build_doctrine_usage(raw)

    assert usage == {
        100: [
            {"ship_name": "Ferox", "fit_qty": 2, "fits_on_mkt": 5},
            {"ship_name": "Drake", "fit_qty": 3, "fits_on_mkt": 4},
        ],
        200: [{"ship_name": "Drake", "fit_qty": 1, "fits_on_mkt": 9}],
    }


def test_collapses_identical_usage_rows():
    # Two fits of the same hull with the same qty and stock read as one line,
    # matching the old SELECT DISTINCT ship_name, fit_qty, fits_on_mkt.
    raw = _raw_df([
        (1, 100, "Ferox", 2, 5, 10.0),
        (3, 100, "Ferox", 2, 5, 10.0),
    ])

    assert build_doctrine_usage(raw) == {
        100: [{"ship_name": "Ferox", "fit_qty": 2, "fits_on_mkt": 5}],
    }


def test_type_ids_are_python_ints():
    raw = _raw_df([(1, 100, "Ferox", 2, 5, 10.0)])

    (type_id,) = build_doctrine_usage(raw)

    assert type(type_id) is int


def test_empty_or_missing_columns_returns_empty():
    assert build_doctrine_usage(pd.DataFrame()) == {}
    assert build_doctrine_usage(pd.DataFrame({"type_id": [1]})) == {}
