#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from services.ai.privacy_guard import (
    contains_prohibited_sensitive_fields,
    sanitize_metadata,
    validate_external_ai_payload,
)


def check(name, condition):
    print(("PASS" if condition else "FAIL"), name)
    return 0 if condition else 1


failures = 0
payload = {
    "email": "user@example.com",
    "nested": {"access_token": "secret", "ok": "value"},
    "list": [{"phone": "+264 81 000 0000"}, {"tag": "music"}],
}
sanitized = sanitize_metadata(payload)
failures += check("privacy recursively removes prohibited fields", "email" not in sanitized and "access_token" not in sanitized.get("nested", {}))
failures += check("privacy keeps safe fields", sanitized.get("nested", {}).get("ok") == "value")
failures += check("privacy strips prohibited list entries", "phone" not in (sanitized.get("list") or [{}])[0])
failures += check("detects prohibited fields in raw payload", contains_prohibited_sensitive_fields(payload) is True)
try:
    validate_external_ai_payload(payload)
    failures += check("unsafe payload rejected", False)
except ValueError:
    failures += check("unsafe payload rejected", True)

safe_payload = {"topic": "music", "metadata": {"region": "khomas"}}
validated = validate_external_ai_payload(safe_payload)
failures += check("safe payload accepted", validated.get("topic") == "music")

sys.exit(1 if failures else 0)
