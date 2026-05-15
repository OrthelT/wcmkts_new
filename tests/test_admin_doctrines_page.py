"""Regression tests for admin doctrine page source-level UI constraints."""

from pathlib import Path


def test_delete_confirmation_is_not_trapped_inside_disabled_form_submit():
    source = Path("pages/admin_doctrines.py").read_text(encoding="utf-8")

    assert 'with st.form("admin_delete_doctrine_fit_form")' not in source
    assert 'form_submit_button(\n                "Delete Fit"' not in source
