"""
Active Language State Management

Stores the current UI language in Streamlit session state and URL query params.
"""

import streamlit as st

from settings_service import SettingsService

DEFAULT_LANGUAGE = SettingsService().default_language
LANGUAGE_STATE_KEY = "active_language"
LANGUAGE_QUERY_PARAM_KEY = "lang"


def get_active_language() -> str:
    """Return the current UI language code."""
    return st.session_state.get(LANGUAGE_STATE_KEY, DEFAULT_LANGUAGE)


def set_active_language(language_code: str) -> None:
    """Set the current UI language code."""
    st.session_state[LANGUAGE_STATE_KEY] = language_code


def set_language_query_param(language_code: str) -> None:
    """Persist the active language into the URL query params."""
    st.query_params[LANGUAGE_QUERY_PARAM_KEY] = language_code


def get_query_param_language() -> str | None:
    """Return the language code from the URL query params, if present."""
    value = st.query_params.get(LANGUAGE_QUERY_PARAM_KEY)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def sync_active_language_with_query_params(valid_languages: list[str]) -> str:
    """Sync the active language between session state and the URL query params.

    Valid query-param values take precedence so bookmarked URLs open in the
    intended language. When the URL is missing or invalid, the current session
    language is written back into the URL to keep links shareable.
    """
    fallback_language = (
        DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in valid_languages else valid_languages[0]
    )
    query_language = get_query_param_language()
    if query_language in valid_languages:
        if get_active_language() != query_language:
            set_active_language(query_language)
        return query_language

    current_language = get_active_language()
    if current_language not in valid_languages:
        current_language = fallback_language
        set_active_language(current_language)

    set_language_query_param(current_language)
    return current_language
