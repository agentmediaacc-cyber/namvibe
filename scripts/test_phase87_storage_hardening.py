"""Phase 87 — Storage Hardening Test."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage_health_service import (
    check_supabase_storage, ensure_required_buckets, get_storage_status,
    safe_upload_file, safe_delete_file,
)

PASS = 0
FAIL = 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("Phase 87: Storage Hardening")

    check("check_supabase_storage exists", callable(check_supabase_storage))
    check("ensure_required_buckets exists", callable(ensure_required_buckets))
    check("get_storage_status exists", callable(get_storage_status))
    check("safe_upload_file exists", callable(safe_upload_file))
    check("safe_delete_file exists", callable(safe_delete_file))

    # safe_upload_file with invalid bucket
    result = safe_upload_file("nonexistent", "test.txt", b"data")
    check("invalid bucket returns error", result.get("error") == "invalid_bucket")

    # safe_upload_file with too large data
    huge = b"x" * (51 * 1024 * 1024)
    result = safe_upload_file("avatars", "test.txt", huge)
    check("too large returns upload_too_large", result.get("error") == "upload_too_large")

    # safe_delete_file with invalid bucket
    result = safe_delete_file("nonexistent", "test.txt")
    check("delete invalid bucket", result.get("error") == "invalid_bucket")

    # get_storage_status returns dict
    status = get_storage_status()
    check("storage status is dict", isinstance(status, dict))

    print(f"\nPhase 87 Storage Hardening: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
