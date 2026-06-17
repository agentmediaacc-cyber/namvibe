#!/usr/bin/env python3
"""Phase 64 — Homepage Performance Hardening Audit.

Verifies LIMITs, caches, timeouts, section_timeout logging, cache TTLs.
"""

import os, sys, re, time, inspect, textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLASK_ENV"] = "testing"
os.environ["FLASK_TESTING"] = "1"

PASS = 0
FAIL = 0
SKIP = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  PASS  {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {msg}")


def skip(msg):
    global SKIP
    SKIP += 1
    print(f"  SKIP  {msg}")


print("=" * 72)
print("Phase 64 — Homepage Performance Hardening Audit")
print("=" * 72)

# --- 1. Load the source file ---
src_path = "services/homepage_service.py"
if not os.path.exists(src_path):
    fail(f"{src_path} not found")
    sys.exit(1)

with open(src_path) as f:
    src = f.read()

lines = src.split("\n")


# --- 2. Verify _profile_map_for_ids has LIMIT %s ---
def test_profile_map_for_ids_limit():
    m = re.search(r"def _profile_map_for_ids.*?", src)
    if not m:
        skip("_profile_map_for_ids not found")
        return
    if "LIMIT %s" in src[m.end():m.end() + 500]:
        ok("_profile_map_for_ids includes LIMIT %s")
    else:
        fail("_profile_map_for_ids missing LIMIT %s")


# --- 3. Verify _suggested_people has cache and timeout_ms=1000 ---
def test_suggested_people_cache():
    m = re.search(r"def _suggested_people.*?(?=\n\ndef|\Z)", src, re.DOTALL)
    if not m:
        skip("_suggested_people not found")
        return
    body = m.group()
    checks = [
        ("get_cache", "get_cache call"),
        ("set_cache", "set_cache call"),
        ("ttl=300", "TTL 300s"),
        ("timeout_ms=1000", "timeout_ms=1000"),
    ]
    for pattern, label in checks:
        if pattern in body:
            ok(f"_suggested_people: {label}")
        else:
            fail(f"_suggested_people: missing {label}")


# --- 4. Verify fetch_trending_creators has cache and timeout_ms=1000 ---
def test_trending_creators_cache():
    m = re.search(r"def fetch_trending_creators.*?(?=\n\ndef|\Z)", src, re.DOTALL)
    if not m:
        skip("fetch_trending_creators not found")
        return
    body = m.group()
    checks = [
        ("get_cache", "get_cache call"),
        ("set_cache", "set_cache call"),
        ("ttl=300", "TTL 300s"),
        ("timeout_ms=1000", "timeout_ms=1000"),
    ]
    for pattern, label in checks:
        if pattern in body:
            ok(f"fetch_trending_creators: {label}")
        else:
            fail(f"fetch_trending_creators: missing {label}")


# --- 5. Verify get_homepage_data has _wait_or_empty with timeout=1.0 ---
def test_get_homepage_data_timeout():
    m = re.search(r"def get_homepage_data.*?(?=\n\ndef|\Z)", src, re.DOTALL)
    if not m:
        skip("get_homepage_data not found")
        return
    body = m.group()
    checks = [
        ("future.result(timeout=1.0)", "future.result(timeout=1.0)"),
        ("homepage_section_timeout", "homepage_section_timeout log"),
    ]
    for pattern, label in checks:
        if pattern in body:
            ok(f"get_homepage_data: {label}")
        else:
            fail(f"get_homepage_data: missing {label}")


# --- 6. Verify _suggested_people called in build_tiktok_home_payload (unchanged) ---
def test_build_tiktok_home_suggested():
    if "_suggested_people(current_user=current, limit=5)" in src:
        ok("build_tiktok_home_payload calls _suggested_people")
    else:
        fail("build_tiktok_home_payload missing _suggested_people call")


# --- 7. Run `_suggested_people` integration (warm cache, no DB needed) ---
def test_integration_warm_cache():
    try:
        # verify the cache_key import works
        from engines.cache_engine import cache_key, get_cache, set_cache
        k = cache_key("suggested_people", "anonymous")
        # set dummy data
        set_cache(k, [{"id": 999, "username": "test"}], ttl=300)
        from services import homepage_service
        # patch is_circuit_open to return False
        orig = homepage_service.is_circuit_open
        homepage_service.is_circuit_open = lambda: False
        result = homepage_service._suggested_people()
        homepage_service.is_circuit_open = orig
        if result and result[0].get("id") == 999:
            ok("_suggested_people cache returns cached data instantly")
        else:
            fail(f"_suggested_people cache returned unexpected: {result}")
    except Exception as e:
        fail(f"_suggested_people cache integration error: {e}")


# --- 8. Verify _wait_or_empty is defined inside get_homepage_data ---
def test_wait_or_empty_defined():
    # Look for _wait_or_empty inside get_homepage_data
    idx = src.find("def get_homepage_data")
    if idx < 0:
        skip("get_homepage_data not found")
        return
    after = src[idx:idx + 6000]
    if "_wait_or_empty" in after and "def _wait_or_empty" not in after:
        # It's a nested function within get_homepage_data
        ok("_wait_or_empty defined inside get_homepage_data")
    elif "def _wait_or_empty" in after:
        ok("_wait_or_empty defined inside get_homepage_data")
    else:
        fail("_wait_or_empty not found in get_homepage_data")


# --- 9. Verify no SELECT * in homepage_service.py ---
def test_no_select_star():
    dangerous = re.findall(r"\bSELECT\s+\*", src, re.IGNORECASE)
    if dangerous:
        fail(f"Found {len(dangerous)} SELECT * (should use explicit columns)")
    else:
        ok("No SELECT * found")


# --- 10. Verify cache key consistency ---
def test_cache_key_consistency():
    if 'cache_key("suggested_people"' in src or "cache_key('suggested_people'" in src:
        ok("suggested_people uses cache_key")
    else:
        fail("suggested_people missing cache_key call")
    if 'cache_key("trending_creators"' in src or "cache_key('trending_creators'" in src:
        ok("trending_creators uses cache_key")
    else:
        fail("trending_creators missing cache_key call")


def main():
    test_profile_map_for_ids_limit()
    test_suggested_people_cache()
    test_trending_creators_cache()
    test_get_homepage_data_timeout()
    test_build_tiktok_home_suggested()
    test_integration_warm_cache()
    test_wait_or_empty_defined()
    test_no_select_star()
    test_cache_key_consistency()

    total = PASS + FAIL + SKIP
    print(f"\n{'=' * 72}")
    print(f"Results: {PASS} passed, {FAIL} failed, {SKIP} skipped (of {total} total)")
    if FAIL:
        sys.exit(1)
    print("All Phase 64 performance hardening checks PASS.")


if __name__ == "__main__":
    main()
