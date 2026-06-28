#!/usr/bin/env python3
"""
Phase Next — NamVibe Session Configuration Audit.

Imports the app safely, inspects app.config, and verifies that
the effective session cookie configuration is present and sensible.

Usage:
    python3 scripts/audit_namvibe_session_config.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_SCHEDULER", "1")

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        print(f"  ✅  PASS  {label}")
        PASS += 1
    else:
        print(f"  ❌  FAIL  {label}")
        FAIL += 1


def main():
    global PASS, FAIL

    print("\n=== Phase Next: Session Config Audit ===\n")

    # 1. Import app
    try:
        from app import create_app
        app = create_app()
        print("[import] app created successfully\n")
    except Exception as e:
        print(f"[import] FAILED to create app: {e}")
        sys.exit(1)

    cfg = app.config

    # 2. Required session config keys
    required_keys = {
        "SESSION_COOKIE_NAME": str,
        "SESSION_COOKIE_HTTPONLY": bool,
        "SESSION_COOKIE_SAMESITE": str,
        "SESSION_COOKIE_SECURE": bool,
    }

    print("--- Required Session Keys ---")
    for key, expected_type in required_keys.items():
        value = cfg.get(key)
        if value is None:
            check(f"{key} is present", False)
        else:
            check(f"{key} = {repr(value)} (type: {type(value).__name__})", isinstance(value, expected_type))

    # 3. Print effective session config (informational)
    print("\n--- Effective Session Config ---")
    session_keys = [
        "SESSION_COOKIE_NAME",
        "SESSION_COOKIE_HTTPONLY",
        "SESSION_COOKIE_SAMESITE",
        "SESSION_COOKIE_SECURE",
        "SESSION_COOKIE_DOMAIN",
        "PERMANENT_SESSION_LIFETIME",
        "SESSION_REFRESH_EACH_REQUEST",
    ]
    for key in session_keys:
        value = cfg.get(key)
        print(f"    {key} = {repr(value)}")

    # 4. Semantic checks
    print("\n--- Semantic Checks ---")

    secure = cfg.get("SESSION_COOKIE_SECURE")
    samesite = cfg.get("SESSION_COOKIE_SAMESITE")
    http_only = cfg.get("SESSION_COOKIE_HTTPONLY")

    if http_only is True:
        check("SESSION_COOKIE_HTTPONLY is True (prevents JS access)", True)
    else:
        check("SESSION_COOKIE_HTTPONLY is True", False)

    if samesite in ("Lax", "Strict"):
        check(f"SESSION_COOKIE_SAMESITE is '{samesite}' (CSRF protection)", True)
    else:
        check("SESSION_COOKIE_SAMESITE is 'Lax' or 'Strict'", False)

    # In production, SECURE should be True; in dev it's OK to be False
    env = os.getenv("FLASK_ENV", "development")
    if env == "production":
        if secure is True:
            check("SESSION_COOKIE_SECURE is True (production — HTTPS only)", True)
        else:
            check("SESSION_COOKIE_SECURE is True for production", False)
    else:
        print(f"    (dev mode: SESSION_COOKIE_SECURE={secure} is acceptable)")

    # 5. Summary
    total = PASS + FAIL
    print(f"\n=== Results: {PASS}/{total} passed ===\n")
    if FAIL > 0:
        print(f"❌  {FAIL} configuration issue(s) found!\n")
        sys.exit(1)
    else:
        print("✅  Session configuration looks correct.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
