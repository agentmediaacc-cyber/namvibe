"""Phase 88 — Test real Supabase storage upload and delete."""

import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage_health_service import safe_upload_file, safe_delete_file, ensure_required_buckets


def run():
    print("=" * 60)
    print("PHASE 88 — STORAGE UPLOAD/DELETE TEST")
    print("=" * 60)

    # 1. Ensure buckets exist first
    print("\n  Ensuring required buckets exist...")
    result = ensure_required_buckets()
    if not result.get("ok"):
        print(f"  FAIL could not ensure buckets: {result.get('error', 'unknown')}")
        return False
    if result.get("created"):
        print(f"  OK  created buckets: {result['created']}")
    else:
        print("  OK  buckets already present")

    # 2. Upload a tiny test file to a safe test path in the public 'posts' bucket
    test_content = b"phase88_test_upload_delete OK"
    test_path = f"phase88_test_{uuid.uuid4().hex[:12]}.txt"
    bucket = "posts"

    print(f"\n  Uploading test file to {bucket}/{test_path}...")
    upload_result = safe_upload_file(bucket, test_path, test_content, content_type="text/plain")

    if not upload_result.get("ok"):
        print(f"  FAIL upload: {upload_result.get('error', 'unknown')}")
        print(f"\n{'=' * 60}")
        print("PHASE 88: FAIL (upload failed)")
        print(f"{'=' * 60}")
        return False

    url = upload_result.get("url", "")
    if not url or url == f"{bucket}/{test_path}":
        print(f"  FAIL upload returned no real URL (got: {url})")
        safe_delete_file(bucket, test_path)
        print(f"\n{'=' * 60}")
        print("PHASE 88: FAIL (no real URL)")
        print(f"{'=' * 60}")
        return False

    print(f"  OK  upload succeeded, URL: {url}")

    # 3. Delete the test file
    print(f"\n  Deleting test file {bucket}/{test_path}...")
    delete_result = safe_delete_file(bucket, test_path)

    if not delete_result.get("ok"):
        print(f"  FAIL delete: {delete_result.get('error', 'unknown')}")
        print(f"\n{'=' * 60}")
        print("PHASE 88: FAIL (delete failed)")
        print(f"{'=' * 60}")
        return False

    print("  OK  delete succeeded")

    print(f"\n{'=' * 60}")
    print("PHASE 88: PASS (upload + delete confirmed)")
    print(f"{'=' * 60}")
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
