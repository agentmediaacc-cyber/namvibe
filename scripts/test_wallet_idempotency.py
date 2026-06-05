import unittest
from unittest.mock import patch
from decimal import Decimal

from services import wallet_engine
from scripts.test_wallet_atomicity import FakeCursor


class TestWalletIdempotency(unittest.TestCase):
    def test_duplicate_gift_retry_returns_existing_success(self):
        cursor = FakeCursor(initial_balances={"sender": Decimal("100"), "receiver": Decimal("0")})
        cursor.gifts.append(("gift-row", "sender", "receiver", "rose", 25, None, None, "gift-1", "now"))
        with patch("services.wallet_engine.transaction_query", side_effect=lambda callback, timeout_ms=5000, readonly=False: callback(cursor)), \
             patch("services.wallet_engine.create_notification"):
            ok, result = wallet_engine.send_gift("sender", "receiver", "rose", 25, idempotency_key="gift-1")
        self.assertTrue(ok)
        self.assertTrue(result["idempotent"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
