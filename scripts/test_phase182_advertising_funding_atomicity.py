"""Focused regression tests for advertising funding, budget enforcement, and atomic click handling."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services import advertising_service as ads  # noqa: E402


def _assert(label, condition):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.last_query = ""
        self.last_params = None

    def execute(self, query, params=None):
        self.last_query = " ".join(query.split())
        self.last_params = params
        self.state["queries"].append((self.last_query, params))

        if "UPDATE chain_wallets SET balance_cents = balance_cents -" in self.last_query:
            if self.state["wallet"]["balance_cents"] < params[0]:
                self.state["wallet_update_ok"] = False
                return
            self.state["wallet"]["balance_cents"] -= params[0]
            self.state["wallet"]["lifetime_spent_cents"] = self.state["wallet"].get("lifetime_spent_cents", 0) + params[1]
            self.state["wallet_update_ok"] = True
            return

        if "INSERT INTO chain_ad_clicks" in self.last_query:
            self.state["click_inserted"] = True
            return

        if "UPDATE chain_ad_campaigns SET clicks_count" in self.last_query:
            self.state["campaign"]["clicks_count"] = self.state["campaign"].get("clicks_count", 0) + 1
            self.state["campaign"]["spent_amount_cents"] = params[0]
            self.state["campaign"]["daily_spend_cents"] = params[2]
            self.state["campaign"]["status"] = params[3]
            return

        if "DELETE FROM chain_ad_clicks" in self.last_query:
            self.state["rolled_back_click"] = True
            return

        if "UPDATE chain_ad_campaigns SET status = 'pending_payment'" in self.last_query:
            self.state["campaign"]["status"] = "pending_payment"
            return

        if "UPDATE chain_ad_campaigns SET status = 'funded'" in self.last_query:
            self.state["campaign"]["status"] = "funded"
            self.state["campaign"]["funded_amount_cents"] = params[0]
            return

        if "INSERT INTO chain_ad_payments" in self.last_query:
            self.state["payment_inserted"] = True
            self.state["payment_idempotency_key"] = params[7]
            return

        if "INSERT INTO chain_wallet_transactions" in self.last_query:
            self.state["wallet_tx_inserted"] = True
            self.state["wallet_tx_idempotency_key"] = params[7]
            return

    def fetchone(self):
        q = self.last_query
        if "FROM chain_ad_campaigns" in q and "FOR UPDATE" in q:
            return dict(self.state["campaign"])
        if "FROM chain_ad_payments" in q and "idempotency_key" in q:
            return self.state.get("existing_payment")
        if "FROM chain_wallets WHERE profile_id" in q and "FOR UPDATE" in q:
            return dict(self.state["wallet"])
        if "UPDATE chain_wallets SET balance_cents = balance_cents -" in q:
            if self.state.get("wallet_update_ok"):
                return {"balance_cents": self.state["wallet"]["balance_cents"]}
            return None
        if "SELECT id FROM chain_wallets" in q:
            return {"id": self.state["wallet"]["id"]}
        if "SELECT id FROM chain_wallet_transactions WHERE idempotency_key" in q:
            return {"id": "wallet-tx-1"} if self.state.get("wallet_tx_inserted") else None
        if "INSERT INTO chain_ad_clicks" in q and "RETURNING id" in q:
            return {"id": "click-1"}
        if "SELECT COUNT(*) AS cnt FROM chain_ad_clicks c JOIN chain_ad_fraud_events f" in q:
            return {"cnt": 0}
        if "SELECT COUNT(*) AS cnt FROM chain_ad_clicks WHERE campaign_id" in q:
            return {"cnt": 0}
        return None


def _with_transaction(state, callback):
    original_transaction_query = ads.transaction_query

    def fake_transaction_query(fn, timeout_ms=None):
        return fn(FakeCursor(state))

    ads.transaction_query = fake_transaction_query
    try:
        return callback()
    finally:
        ads.transaction_query = original_transaction_query


def test_fund_campaign_succeeds_once():
    state = {
        "queries": [],
        "campaign": {
            "id": "campaign-1",
            "owner_id": "owner-1",
            "title": "Launch",
            "status": "draft",
            "budget_cents": 5000,
            "funded_amount_cents": 0,
        },
        "wallet": {
            "id": "wallet-1",
            "profile_id": "owner-1",
            "balance_cents": 8000,
            "status": "active",
        },
        "existing_payment": None,
    }

    result = _with_transaction(state, lambda: ads.fund_campaign("campaign-1", "owner-1", idempotency_key="pay-1"))
    _assert("funding succeeds", result["ok"] is True)
    _assert("campaign moved to funded", state["campaign"]["status"] == "funded")
    _assert("wallet debited exact amount", state["wallet"]["balance_cents"] == 3000)
    _assert("wallet transaction idempotency stored", state["wallet_tx_idempotency_key"] == "pay-1")


def test_fund_campaign_rejects_insufficient_balance():
    state = {
        "queries": [],
        "campaign": {
            "id": "campaign-2",
            "owner_id": "owner-2",
            "title": "Short",
            "status": "draft",
            "budget_cents": 9000,
            "funded_amount_cents": 0,
        },
        "wallet": {
            "id": "wallet-2",
            "profile_id": "owner-2",
            "balance_cents": 4000,
            "status": "active",
        },
        "existing_payment": None,
    }

    result = _with_transaction(state, lambda: ads.fund_campaign("campaign-2", "owner-2", idempotency_key="pay-2"))
    _assert("insufficient funds error returned", result["error"] == "insufficient_funds")
    _assert("wallet balance unchanged on insufficient funds", state["wallet"]["balance_cents"] == 4000)
    _assert("campaign moved to pending_payment", state["campaign"]["status"] == "pending_payment")


def test_fund_campaign_idempotent_replay():
    state = {
        "queries": [],
        "campaign": {
            "id": "campaign-3",
            "owner_id": "owner-3",
            "title": "Replay",
            "status": "funded",
            "budget_cents": 2500,
            "funded_amount_cents": 2500,
        },
        "wallet": {
            "id": "wallet-3",
            "profile_id": "owner-3",
            "balance_cents": 9000,
            "status": "active",
        },
        "existing_payment": {
            "id": "payment-3",
            "status": "completed",
            "wallet_transaction_id": "wallet-tx-3",
        },
    }

    result = _with_transaction(state, lambda: ads.fund_campaign("campaign-3", "owner-3", idempotency_key="pay-3"))
    _assert("idempotent replay returns success", result["ok"] is True and result.get("idempotent") is True)
    _assert("wallet not debited on idempotent replay", state["wallet"]["balance_cents"] == 9000)


def test_track_click_budget_and_fraud_atomicity():
    state = {
        "queries": [],
        "campaign": {
            "id": "campaign-4",
            "status": "active",
            "funded_amount_cents": 200,
            "spent_amount_cents": 100,
            "daily_budget_cents": 200,
            "daily_spend_cents": 100,
            "bid_amount_cents": 100,
            "starts_at": None,
            "ends_at": None,
            "clicks_count": 0,
        },
        "wallet": {"id": "wallet-4", "profile_id": "owner-4", "balance_cents": 0, "status": "active"},
    }

    original_update_daily_analytics = ads._update_daily_analytics
    original_run_fraud_checks = ads._run_fraud_checks
    analytics_calls = []
    ads._update_daily_analytics = lambda *args, **kwargs: analytics_calls.append((args, kwargs))
    ads._run_fraud_checks = lambda *args, **kwargs: {"is_fraud": False, "fraud_flags": [], "fraud_score": 0}
    try:
        result = _with_transaction(state, lambda: ads.track_click("campaign-4", "viewer-1", "1.1.1.1", "Mozilla/5.0"))
    finally:
        ads._update_daily_analytics = original_update_daily_analytics
        ads._run_fraud_checks = original_run_fraud_checks
    _assert("click under remaining budget succeeds", result["ok"] is True)
    _assert("campaign transitions to budget exhausted at exact cap", state["campaign"]["status"] == "budget_exhausted")
    _assert("analytics written once for valid click", len(analytics_calls) == 1)

    fraud_state = {
        "queries": [],
        "campaign": {
            "id": "campaign-5",
            "status": "active",
            "funded_amount_cents": 1000,
            "spent_amount_cents": 0,
            "daily_budget_cents": 0,
            "daily_spend_cents": 0,
            "bid_amount_cents": 100,
            "starts_at": None,
            "ends_at": None,
            "clicks_count": 0,
        },
        "wallet": {"id": "wallet-5", "profile_id": "owner-5", "balance_cents": 0, "status": "active"},
    }
    original_update_daily_analytics = ads._update_daily_analytics
    original_run_fraud_checks = ads._run_fraud_checks
    ads._update_daily_analytics = lambda *args, **kwargs: analytics_calls.append((args, kwargs))
    ads._run_fraud_checks = lambda *args, **kwargs: {"is_fraud": True, "fraud_flags": [{"type": "bot_traffic"}], "fraud_score": 70}
    try:
        blocked = _with_transaction(fraud_state, lambda: ads.track_click("campaign-5", "viewer-2", "1.1.1.1", "bot"))
    finally:
        ads._update_daily_analytics = original_update_daily_analytics
        ads._run_fraud_checks = original_run_fraud_checks
    _assert("fraudulent click blocked", blocked["ok"] is False and blocked["is_fraud"] is True)
    _assert("fraudulent click rollback executed", fraud_state.get("rolled_back_click") is True)


def run():
    test_fund_campaign_succeeds_once()
    test_fund_campaign_rejects_insufficient_balance()
    test_fund_campaign_idempotent_replay()
    test_track_click_budget_and_fraud_atomicity()
    print("PASS: test_phase182_advertising_funding_atomicity")


if __name__ == "__main__":
    run()
