import unittest
from decimal import Decimal
from unittest.mock import patch

from services import wallet_engine
from scripts.test_wallet_atomicity import FakeCursor


class TestTransactionRollback(unittest.TestCase):
    def test_wallet_rollback_on_failure(self):
        cursor = FakeCursor(initial_balances={"sender": Decimal("100"), "receiver": Decimal("5")}, fail_credit=True)
        before = dict(cursor.balances)

        def fake_transaction_query(callback, timeout_ms=5000, readonly=False):
            snapshot = dict(cursor.balances)
            try:
                callback(cursor)
            except Exception:
                cursor.balances = snapshot
                raise

        with patch("services.wallet_engine.transaction_query", side_effect=fake_transaction_query), \
             patch("services.wallet_engine.create_notification"):
            ok, error = wallet_engine.send_gift("sender", "receiver", "rose", 25, idempotency_key="rollback-1")
        self.assertFalse(ok)
        self.assertEqual(error, "Transaction failed")
        self.assertEqual(cursor.balances, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
