import unittest
from decimal import Decimal
from unittest.mock import patch

from services import wallet_engine


class FakeCursor:
    def __init__(self, initial_balances=None, duplicate_keys=None, fail_credit=False):
        self.balances = dict(initial_balances or {})
        self.duplicate_keys = set(duplicate_keys or set())
        self.fail_credit = fail_credit
        self._fetchone = None
        self.gifts = []
        self.transactions = []

    def execute(self, sql, params=None):
        sql_text = " ".join(str(sql).split())
        params = params or ()

        if "SELECT 1 FROM chain_wallet_transactions WHERE idempotency_key" in sql_text:
            key = params[0]
            self._fetchone = (1,) if key in self.duplicate_keys else None
            return

        if "SELECT id, sender_profile_id, receiver_profile_id, coin_value FROM chain_gifts WHERE idempotency_key" in sql_text:
            key = params[0]
            match = next((gift for gift in self.gifts if gift[-2] == key), None)
            self._fetchone = None if match is None else (match[0], match[1], match[2], match[4])
            return

        if "INSERT INTO chain_wallets" in sql_text:
            profile_id = params[0]
            self.balances.setdefault(profile_id, Decimal("0"))
            self._fetchone = None
            return

        if "SELECT profile_id, coin_balance FROM chain_wallets WHERE profile_id = %s FOR UPDATE" in sql_text:
            profile_id = params[0]
            balance = Decimal(str(self.balances.get(profile_id, Decimal("0"))))
            self._fetchone = (profile_id, balance)
            return

        if "UPDATE chain_wallets SET coin_balance = coin_balance +" in sql_text:
            amount_delta = Decimal(str(params[0]))
            profile_id = params[1]
            if self.fail_credit and amount_delta > 0:
                raise RuntimeError("credit_failed")
            current = Decimal(str(self.balances.get(profile_id, Decimal("0"))))
            new_balance = current + amount_delta
            if new_balance < 0:
                self._fetchone = None
                return
            self.balances[profile_id] = new_balance
            self._fetchone = (new_balance,)
            return

        if "INSERT INTO chain_wallet_transactions" in sql_text:
            key = params[9]
            self.transactions.append(key)
            if key:
                self.duplicate_keys.add(key)
            self._fetchone = (f"tx-{len(self.transactions)}",)
            return

        if "INSERT INTO chain_gifts" in sql_text:
            self.gifts.append(params)
            if len(params) >= 8 and params[7]:
                self.duplicate_keys.add(params[7])
            self._fetchone = None
            return

        if "INSERT INTO chain_wallet_payouts" in sql_text:
            self._fetchone = None
            return

        raise AssertionError(f"Unexpected SQL: {sql_text}")

    def fetchone(self):
        return self._fetchone

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self):
        return self.cursor_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestWalletAtomicity(unittest.TestCase):
    def test_atomic_gift_transfer_updates_both_wallets(self):
        cursor = FakeCursor(initial_balances={"sender": Decimal("100"), "receiver": Decimal("5")})
        with patch("services.wallet_engine.transaction_query", side_effect=lambda callback, timeout_ms=5000: callback(cursor)), \
             patch("services.wallet_engine.create_notification"):
            ok, result = wallet_engine.send_gift("sender", "receiver", "rose", 25, entity_type="live_room", entity_id="room-1", idempotency_key="gift-1")
        self.assertTrue(ok)
        self.assertFalse(result["idempotent"])
        self.assertEqual(cursor.balances["sender"], Decimal("75"))
        self.assertEqual(cursor.balances["receiver"], Decimal("30"))
        self.assertEqual(len(cursor.transactions), 2)
        self.assertEqual(len(cursor.gifts), 1)

    def test_negative_balance_prevention(self):
        cursor = FakeCursor(initial_balances={"sender": Decimal("10"), "receiver": Decimal("0")})
        with patch("services.wallet_engine.transaction_query", side_effect=lambda callback, timeout_ms=5000: callback(cursor)), \
             patch("services.wallet_engine.create_notification"):
            ok, error = wallet_engine.send_gift("sender", "receiver", "rose", 25, idempotency_key="gift-2")
        self.assertFalse(ok)
        self.assertEqual(error, "Insufficient balance")
        self.assertEqual(cursor.balances["sender"], Decimal("10"))
        self.assertEqual(cursor.balances["receiver"], Decimal("0"))

    def test_idempotent_retry_is_safe(self):
        cursor = FakeCursor(initial_balances={"sender": Decimal("100"), "receiver": Decimal("0")})
        cursor.gifts.append(("gift-row", "sender", "receiver", "rose", 25, None, None, "gift-3", "now"))
        with patch("services.wallet_engine.transaction_query", side_effect=lambda callback, timeout_ms=5000: callback(cursor)), \
             patch("services.wallet_engine.create_notification"):
            ok, result = wallet_engine.send_gift("sender", "receiver", "rose", 25, idempotency_key="gift-3")
        self.assertTrue(ok)
        self.assertTrue(result["idempotent"])
        self.assertEqual(cursor.balances["sender"], Decimal("100"))
        self.assertEqual(cursor.balances["receiver"], Decimal("0"))
        self.assertEqual(cursor.transactions, [])

    def test_payout_pending_idempotent(self):
        cursor = FakeCursor(initial_balances={"creator": Decimal("80")})
        with patch("services.wallet_engine.transaction_query", side_effect=lambda callback, timeout_ms=5000: callback(cursor)):
            ok, status = wallet_engine.request_payout("creator", 20, idempotency_key="payout-1")
        self.assertTrue(ok)
        self.assertEqual(status, "pending")
        self.assertEqual(cursor.balances["creator"], Decimal("60"))

    def test_simulated_failure_rolls_back(self):
        cursor = FakeCursor(initial_balances={"sender": Decimal("100"), "receiver": Decimal("5")}, fail_credit=True)
        snapshot = dict(cursor.balances)

        def fake_transaction_query(callback, timeout_ms=5000):
            before = dict(cursor.balances)
            try:
                callback(cursor)
            except Exception:
                cursor.balances = before
                raise

        with patch("services.wallet_engine.transaction_query", side_effect=fake_transaction_query), \
             patch("services.wallet_engine.create_notification"):
            ok, error = wallet_engine.send_gift("sender", "receiver", "rose", 25, idempotency_key="gift-rollback")
        self.assertFalse(ok)
        self.assertEqual(error, "Transaction failed")
        self.assertEqual(cursor.balances, snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
