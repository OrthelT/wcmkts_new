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

    def test_no_params_no_state_returns_none_none(self):
        assert self._call({}, {}) == (None, None)
