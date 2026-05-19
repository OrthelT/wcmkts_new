"""Regression tests for admin doctrine page source-level UI constraints."""

from pathlib import Path


def test_delete_confirmation_is_not_trapped_inside_disabled_form_submit():
    source = Path("pages/admin_doctrines.py").read_text(encoding="utf-8")

    assert 'with st.form("admin_delete_doctrine_fit_form")' not in source
    assert 'form_submit_button(\n                "Delete Fit"' not in source


def test_rename_doctrine_form_calls_service_rename():
    source = Path("pages/admin_doctrines.py").read_text(encoding="utf-8")
    assert 'st.form(f"admin_rename_doctrine_form_{selected_doctrine_id}")' in source
    assert "service.rename_doctrine(" in source


def test_admin_pages_use_translation_helpers():
    for page_path in (
        "pages/admin.py",
        "pages/admin_doctrines.py",
        "pages/admin_login.py",
    ):
        source = Path(page_path).read_text(encoding="utf-8")
        assert "get_active_language" in source
        assert "translate_text" in source
