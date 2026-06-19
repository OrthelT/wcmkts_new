"""Unit tests for the durable deep-link filter resolver in doctrine_status."""


class TestResolveDeeplinkFilter:
    """resolve_deeplink_filter consumes the URL param once, then persists it in
    session_state so the filter survives later reruns."""

    def _call(self, query_params, session_state):
        from pages.doctrine_status import resolve_deeplink_filter

        return resolve_deeplink_filter(query_params, session_state)

    def test_ship_param_is_stored_and_url_cleared(self):
        qp, ss = {"ship_id": "603"}, {}
        assert self._call(qp, ss) == (603, None)
        assert ss["ds_deeplink_ship_id"] == 603
        assert "ship_id" not in qp  # consumed from the URL

    def test_module_param_is_stored_and_url_cleared(self):
        qp, ss = {"module_id": "13001"}, {}
        assert self._call(qp, ss) == (None, 13001)
        assert ss["ds_deeplink_module_id"] == 13001
        assert "module_id" not in qp

    def test_falls_back_to_persisted_ship_when_no_param(self):
        qp, ss = {}, {"ds_deeplink_ship_id": 603}
        assert self._call(qp, ss) == (603, None)

    def test_falls_back_to_persisted_module_when_no_param(self):
        qp, ss = {}, {"ds_deeplink_module_id": 13001}
        assert self._call(qp, ss) == (None, 13001)

    def test_new_module_param_overrides_persisted_ship(self):
        qp, ss = {"module_id": "13001"}, {"ds_deeplink_ship_id": 603}
        assert self._call(qp, ss) == (None, 13001)
        assert "ds_deeplink_ship_id" not in ss  # other kind cleared

    def test_new_ship_param_overrides_persisted_module(self):
        qp, ss = {"ship_id": "603"}, {"ds_deeplink_module_id": 13001}
        assert self._call(qp, ss) == (603, None)
        assert "ds_deeplink_module_id" not in ss

    def test_invalid_int_is_ignored_but_param_consumed(self):
        qp, ss = {"ship_id": "not-a-number"}, {}
        assert self._call(qp, ss) == (None, None)
        assert "ship_id" not in qp
        assert "ds_deeplink_ship_id" not in ss

    def test_ship_wins_when_both_params_present(self):
        # Documented precedence: ship wins, and both params are consumed.
        qp, ss = {"ship_id": "603", "module_id": "13001"}, {}
        assert self._call(qp, ss) == (603, None)
        assert "ship_id" not in qp and "module_id" not in qp
        assert ss["ds_deeplink_ship_id"] == 603
        assert "ds_deeplink_module_id" not in ss

    def test_no_params_no_state_returns_none_none(self):
        assert self._call({}, {}) == (None, None)


class TestClearDeeplinkFilter:
    """_clear_deeplink_filter (the 'Show all fits' button) drops both keys."""

    def test_clears_both_keys(self):
        from unittest.mock import patch

        from pages import doctrine_status as ds

        state = {"ds_deeplink_ship_id": 603, "ds_deeplink_module_id": 13001}
        with patch.object(ds.st, "session_state", state):
            ds._clear_deeplink_filter()
        assert state == {}

    def test_is_a_noop_when_no_filter_active(self):
        from unittest.mock import patch

        from pages import doctrine_status as ds

        state = {"unrelated": 1}
        with patch.object(ds.st, "session_state", state):
            ds._clear_deeplink_filter()
        assert state == {"unrelated": 1}


class TestClearDeeplinkModule:
    """_clear_deeplink_module drops only the module key — used when a deep-linked
    module turns out to have no fit info — leaving any ship filter intact."""

    def test_clears_only_module_key(self):
        from unittest.mock import patch

        from pages import doctrine_status as ds

        state = {"ds_deeplink_module_id": 13001}
        with patch.object(ds.st, "session_state", state):
            ds._clear_deeplink_module()
        assert state == {}

    def test_leaves_ship_key_untouched(self):
        from unittest.mock import patch

        from pages import doctrine_status as ds

        state = {"ds_deeplink_ship_id": 603}
        with patch.object(ds.st, "session_state", state):
            ds._clear_deeplink_module()
        assert state == {"ds_deeplink_ship_id": 603}

    def test_invalid_module_cleared_so_next_visit_is_not_stuck(self):
        # Reproduces the stale-bookmark stuck loop: a module_id is persisted on
        # the first visit, proves invalid (no fit info), is cleared before
        # st.stop(), and a later param-less visit no longer re-applies the bad
        # filter (the page would otherwise be stuck on the error every visit).
        from unittest.mock import patch

        from pages import doctrine_status as ds

        ss = {}
        assert ds.resolve_deeplink_filter({"module_id": "999999"}, ss) == (None, 999999)
        assert ss["ds_deeplink_module_id"] == 999999
        # main() discovers empty fit info -> clears the bad key before stopping.
        with patch.object(ds.st, "session_state", ss):
            ds._clear_deeplink_module()
        # Next visit with no query params must NOT re-apply the stale filter.
        assert ds.resolve_deeplink_filter({}, ss) == (None, None)


class TestClearDeeplinkShip:
    """_clear_deeplink_ship drops only the ship key — used when a deep-linked
    ship matches no fits (e.g. a bookmark from another market) — leaving any
    module filter intact."""

    def test_clears_only_ship_key(self):
        from unittest.mock import patch

        from pages import doctrine_status as ds

        state = {"ds_deeplink_ship_id": 603}
        with patch.object(ds.st, "session_state", state):
            ds._clear_deeplink_ship()
        assert state == {}

    def test_leaves_module_key_untouched(self):
        from unittest.mock import patch

        from pages import doctrine_status as ds

        state = {"ds_deeplink_module_id": 13001}
        with patch.object(ds.st, "session_state", state):
            ds._clear_deeplink_ship()
        assert state == {"ds_deeplink_module_id": 13001}

    def test_unmatched_ship_cleared_so_next_visit_is_clean(self):
        # A bookmarked ship that matches nothing in the current market lingers
        # invisibly (shows all fits, no banner/clear button). Clearing it on the
        # empty-match path keeps the next param-less visit clean.
        from unittest.mock import patch

        from pages import doctrine_status as ds

        ss = {}
        assert ds.resolve_deeplink_filter({"ship_id": "603"}, ss) == (603, None)
        assert ss["ds_deeplink_ship_id"] == 603
        with patch.object(ds.st, "session_state", ss):
            ds._clear_deeplink_ship()
        assert ds.resolve_deeplink_filter({}, ss) == (None, None)
