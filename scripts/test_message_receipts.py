#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(label, condition):
    print(("PASS" if condition else "FAIL") + f": {label}")
    if not condition:
        raise AssertionError(label)


def main():
    import services.message_receipt_service as receipts

    writes = []

    def fake_fast_query(sql, params=None, default=None, **kwargs):
        if "FROM chain_messages" in sql:
            return [{"id": "msg-1", "thread_id": "thread-1", "sender_profile_id": "sender-1"}]
        return default if default is not None else []

    def fake_write_query(sql, params=None, **kwargs):
        writes.append(sql)
        return []

    receipts.fast_query = fake_fast_query
    receipts.write_query = fake_write_query
    receipts.can_access_thread = lambda profile_id, thread_id: True

    delivered = receipts.mark_message_delivered("msg-1", "receiver-1")
    seen = receipts.mark_message_seen("msg-1", "receiver-1")

    combined = "\n".join(writes)
    check("mark delivered ok", delivered.get("ok") and delivered.get("status") == "delivered")
    check("mark seen ok", seen.get("ok") and seen.get("status") == "seen")
    check("receipt timestamps written", "delivered_at" in combined and "seen_at" in combined)
    check("duplicate receipt update does not create duplicate rows", "ON CONFLICT (message_id, user_id)" in combined)
    check("unread count decreases after seen via thread last_read", "last_read_at" in combined and "is_seen = TRUE" in combined)
    print("test_message_receipts_ok")


if __name__ == "__main__":
    main()
