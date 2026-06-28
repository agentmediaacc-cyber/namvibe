#!/usr/bin/env python3
"""
Phase Next — NamVibe Runtime Route Audit.

Imports the app safely, enumerates all registered Flask routes,
and verifies that required production routes exist.

Usage:
    python3 scripts/audit_namvibe_runtime_routes.py
"""

import os
import sys

# Ensure we can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Safe environment for local import
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

    # 1. Import app
    print("\n=== Phase Next: Runtime Route Audit ===\n")

    try:
        from app import create_app
        app = create_app()
        print("[import] app created successfully\n")
    except Exception as e:
        print(f"[import] FAILED to create app: {e}")
        sys.exit(1)

    # 2. Collect all registered routes
    all_routes = set()
    for rule in app.url_map.iter_rules():
        if rule.rule and not rule.rule.startswith("/static"):
            all_routes.add(rule.rule)

    # Sort for readable output
    sorted_routes = sorted(all_routes)
    print(f"Total non-static routes registered: {len(sorted_routes)}\n")

    # Optional: print all routes for reference (limit to avoid noise)
    print("--- All Routes ---")
    for r in sorted_routes:
        print(f"    {r}")
    print("---\n")

    # 3. Check required production routes
    print("--- Required Route Checks ---")

    required_routes = [
        "/login",
        "/auth/login",
        "/healthz",
        "/notifications",
        "/messages",
        "/profile",
        "/discover",
    ]

    # Normalize: ensure trailing-slash variants are considered
    route_variants = set()
    for r in all_routes:
        route_variants.add(r)
        if r.endswith("/"):
            route_variants.add(r.rstrip("/"))
        else:
            route_variants.add(r + "/")

    for route in required_routes:
        # Check exact match or with/without trailing slash
        found = route in all_routes
        if not found:
            # Try common prefixes / suffixes
            for r in all_routes:
                if r == route or r.rstrip("/") == route.rstrip("/"):
                    found = True
                    break
        check(f"Route '{route}' exists", found)

    # 4. Summary
    total = PASS + FAIL
    print(f"\n=== Results: {PASS}/{total} passed ===\n")
    if FAIL > 0:
        print(f"❌  {FAIL} critical route(s) missing!\n")
        sys.exit(1)
    else:
        print("✅  All required routes present.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
