"""Tests for language state and query-param synchronization."""

from state import language_state


def test_sync_active_language_with_query_params_prefers_valid_query_language(monkeypatch):
    monkeypatch.setattr(language_state.st, "session_state", {}, raising=False)
    monkeypatch.setattr(
        language_state.st,
        "query_params",
        {"lang": "de"},
        raising=False,
    )

    result = language_state.sync_active_language_with_query_params(["en", "de", "zh"])

    assert result == "de"
    assert language_state.st.session_state["active_language"] == "de"


def test_sync_active_language_with_query_params_writes_session_language_to_url(monkeypatch):
    monkeypatch.setattr(
        language_state.st,
        "session_state",
        {"active_language": "fr"},
        raising=False,
    )
    monkeypatch.setattr(language_state.st, "query_params", {}, raising=False)

    result = language_state.sync_active_language_with_query_params(["en", "fr", "ru"])

    assert result == "fr"
    assert language_state.st.query_params["lang"] == "fr"
