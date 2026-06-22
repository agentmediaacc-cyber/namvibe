#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE134 = [
    "scripts/phase134_test_auth_utils.py",
    "scripts/test_phase134_disposable_accounts.py",
    "scripts/setup_phase134_test_thread.py",
    "scripts/test_phase134_authenticated_messaging_flow.py",
    "scripts/test_phase134_authenticated_media_flow.py",
    "scripts/test_phase134_authenticated_voice_note_flow.py",
    "scripts/test_phase134_authenticated_call_flow.py",
    "scripts/test_phase134_authenticated_notification_flow.py",
    "scripts/test_phase134_authenticated_group_flow.py",
    "scripts/cleanup_phase134_test_data.py",
    "scripts/run_phase134_authenticated_e2e.py",
    "scripts/audit_phase134_e2e_safety.py",
]
PASS = FAIL = WARN = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


def read(path):
    full = ROOT / path
    return full.read_text(encoding="utf-8", errors="ignore") if full.exists() else ""


print("=" * 60)
print("PHASE 134 - E2E SAFETY AUDIT")
print("=" * 60)

for path in PHASE134:
    ok(f"{path} exists") if (ROOT / path).exists() else fail(f"{path} missing")

combined = "\n".join(read(path) for path in PHASE134)
gitignore = read(".gitignore")

if re.search(r"(pass(word)?|pwd)\s*=\s*['\"][^'\"\n]{6,}['\"]", combined, re.I):
    fail("possible hardcoded password assignment")
else:
    ok("no hardcoded password literals detected")

emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", combined)
bad_emails = [email for email in emails if not email.endswith("example.com")]
if bad_emails:
    fail("non-example hardcoded emails: " + ", ".join(sorted(set(bad_emails))[:5]))
else:
    ok("no real hardcoded emails")

ok("PHASE134_TEST_ prefix used") if "PHASE134_TEST_" in combined else fail("PHASE134_TEST_ prefix missing")
ok("PHASE134_TEST_GROUP_ prefix used") if "PHASE134_TEST_GROUP_" in combined else fail("PHASE134_TEST_GROUP_ prefix missing")
ok("cleanup requires --confirm") if "--confirm" in read("scripts/cleanup_phase134_test_data.py") else fail("cleanup confirm flag missing")
ok("credentials loaded from env/secrets only") if "NAMVIBE_TEST_USER_A" in combined and "secrets/test_credentials.json" in combined else fail("credential source rules missing")
ok("secrets/test_credentials.json ignored") if "secrets/" in gitignore else fail("secrets/ not ignored")
ok("tmp context excludes passwords") if "password" in read("scripts/phase134_test_auth_utils.py") and "clean =" in read("scripts/phase134_test_auth_utils.py") else fail("tmp context password scrub missing")
ok("cleanup refuses non-test data") if "PHASE134_TEST_" in read("scripts/cleanup_phase134_test_data.py") else fail("cleanup lacks test prefix guard")
password_print = re.search(r"print\([^)]*(password|passwd|NAMVIBE_TEST_PASS|user\.get\([\"']password)", combined, re.I)
ok("scripts avoid printing passwords") if not password_print else fail("possible password print")

dangerous_delete = re.search(r"DELETE\s+FROM|\.delete\(|safe_delete\(", combined, re.I)
if dangerous_delete:
    fail("uncontrolled direct delete-like operation detected")
else:
    ok("no uncontrolled direct DELETE operations")

print(f"\n{'=' * 60}")
print("PHASE 134 - E2E SAFETY AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
