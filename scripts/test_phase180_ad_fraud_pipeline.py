"""Focused regression tests for advertising fraud-event normalization and click linkage."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services import advertising_service as ads  # noqa: E402


def _assert(label, condition):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def test_normalize_details():
    _assert(
        "normalize handles None",
        ads.normalize_fraud_event_details(None) == {"click_id": None, "flags": []},
    )
    _assert(
        "normalize handles malformed string",
        ads.normalize_fraud_event_details("{bad json") == {"click_id": None, "flags": []},
    )
    legacy = [{"type": "bot_traffic", "detail": "legacy"}]
    _assert(
        "normalize preserves legacy array flags",
        ads.normalize_fraud_event_details(legacy) == {"click_id": None, "flags": legacy},
    )
    obj = {"click_id": "abc", "flags": [{"type": "duplicate_click", "detail": "new"}]}
    _assert(
        "normalize preserves new object",
        ads.normalize_fraud_event_details(obj) == obj,
    )


def test_check_fraud_writes_click_id_and_safe_join():
    original_fast_query = ads.fast_query
    original_write_query = ads.write_query
    seen_sql = []
    writes = []

    def fake_fast_query(query, params=None, default=None, **kwargs):
        seen_sql.append(query)
        if "JOIN chain_ad_fraud_events" in query:
            return [{"cnt": 51}]
        if "FROM chain_ad_clicks" in query:
            return [{"cnt": 4}]
        return default if default is not None else []

    def fake_write_query(query, params=None, **kwargs):
        writes.append((query, params))
        return []

    ads.fast_query = fake_fast_query
    ads.write_query = fake_write_query
    try:
        result = ads.check_fraud(
            "campaign-1",
            "profile-1",
            ip_address="127.0.0.1",
            user_agent="python-requests/2.0",
            click_id="click-123",
        )
    finally:
        ads.fast_query = original_fast_query
        ads.write_query = original_write_query

    _assert("fraud result marked fraudulent", result["is_fraud"] is True)
    _assert("multiple fraud flags preserved", len(result["fraud_flags"]) >= 2)
    join_sql = next(sql for sql in seen_sql if "JOIN chain_ad_fraud_events" in sql)
    _assert("safe click join retained", "c.id::text = f.details->>'click_id'" in join_sql)
    _assert("unsafe uuid cast not introduced", "::uuid" not in join_sql)
    insert = next((params for query, params in writes if "INSERT INTO chain_ad_fraud_events" in query), None)
    details = json.loads(insert[-1])
    _assert("fraud write stores click_id", details["click_id"] == "click-123")
    _assert("fraud write stores flags array", details["flags"] == result["fraud_flags"])


def test_get_fraud_events_normalizes_output():
    original_fast_query = ads.fast_query

    def fake_fast_query(query, params=None, default=None, **kwargs):
        return [
            {"id": "1", "details": [{"type": "bot_traffic", "detail": "legacy"}]},
            {"id": "2", "details": {"click_id": "click-2", "flags": [{"type": "duplicate_click", "detail": "new"}]}},
            {"id": "3", "details": None},
            {"id": "4", "details": "not json"},
        ]

    ads.fast_query = fake_fast_query
    try:
        rows = ads.get_fraud_events(limit=4)
    finally:
        ads.fast_query = original_fast_query

    _assert("legacy rows keep null click_id", rows[0]["click_id"] is None)
    _assert("legacy rows expose normalized flags", rows[0]["flags"] == [{"type": "bot_traffic", "detail": "legacy"}])
    _assert("new rows expose click_id", rows[1]["click_id"] == "click-2")
    _assert("new rows expose flags", rows[1]["flags"] == [{"type": "duplicate_click", "detail": "new"}])
    _assert("missing details normalize", rows[2]["details"] == {"click_id": None, "flags": []})
    _assert("malformed details normalize", rows[3]["details"] == {"click_id": None, "flags": []})


def test_track_click_rolls_back_only_for_fraud():
    original_transaction_query = ads.transaction_query
    original_chargeable_campaign = ads._chargeable_campaign
    original_run_fraud_checks = ads._run_fraud_checks
    original_rollback_click = ads.rollback_click
    original_update_daily_analytics = ads._update_daily_analytics
    calls = {"rollback": [], "analytics": []}

    class FakeCursor:
        def __init__(self):
            self.inserted_click_id = "click-xyz"
            self.last_query = ""

        def execute(self, query, params=None):
            self.last_query = query

        def fetchone(self):
            if "RETURNING id" in self.last_query:
                return {"id": self.inserted_click_id}
            return {"cnt": 0}

    def fake_transaction_query(callback, timeout_ms=None):
        return callback(FakeCursor())

    ads.transaction_query = fake_transaction_query
    ads._chargeable_campaign = lambda cursor, campaign_id: {
        "id": campaign_id,
        "status": "active",
        "funded_amount_cents": 1000,
        "spent_amount_cents": 0,
        "daily_budget_cents": 0,
        "daily_spend_cents": 0,
        "bid_amount_cents": 100,
        "starts_at": None,
        "ends_at": None,
    }
    ads.rollback_click = lambda campaign_id, click_id, charge_cents=0, cursor=None: calls["rollback"].append((campaign_id, click_id, charge_cents)) or True
    ads._update_daily_analytics = lambda *args, **kwargs: calls["analytics"].append((args, kwargs))
    try:
        ads._run_fraud_checks = lambda *args, **kwargs: {"is_fraud": False, "fraud_flags": [], "fraud_score": 0}
        ok_result = ads.track_click("campaign-ok", "profile-ok", "1.1.1.1", "Mozilla/5.0")
        _assert("non-fraud click succeeds", ok_result["ok"] is True and ok_result["click_id"] == "click-xyz")
        _assert("non-fraud click does not rollback", calls["rollback"] == [])
        _assert("non-fraud click updates analytics", len(calls["analytics"]) == 1)

        ads._run_fraud_checks = lambda *args, **kwargs: {"is_fraud": True, "fraud_flags": [{"type": "bot_traffic"}], "fraud_score": 70}
        blocked = ads.track_click("campaign-block", "profile-block", "1.1.1.1", "bot-agent")
        _assert("fraud click blocked", blocked["ok"] is False and blocked["is_fraud"] is True)
        _assert("fraud click rolled back", calls["rollback"] == [("campaign-block", "click-xyz", 100)])
    finally:
        ads.transaction_query = original_transaction_query
        ads._chargeable_campaign = original_chargeable_campaign
        ads._run_fraud_checks = original_run_fraud_checks
        ads.rollback_click = original_rollback_click
        ads._update_daily_analytics = original_update_daily_analytics


def run():
    test_normalize_details()
    test_check_fraud_writes_click_id_and_safe_join()
    test_get_fraud_events_normalizes_output()
    test_track_click_rolls_back_only_for_fraud()
    print("PASS: test_phase180_ad_fraud_pipeline")


if __name__ == "__main__":
    run()
