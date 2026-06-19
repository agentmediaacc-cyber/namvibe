"""Phase 88 — Ensure all required Supabase storage buckets exist.

Creates missing buckets only. Never deletes or overwrites existing buckets.
Public/private visibility follows the naming rules in storage_health_service.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_client import get_supabase_admin

REQUIRED_BUCKETS = [
    "avatars", "covers", "posts", "reels", "stories",
    "voice-notes", "messages", "documents", "thumbnails",
]

PUBLIC_BUCKETS = {"avatars", "covers", "posts", "reels", "stories", "thumbnails"}
PRIVATE_BUCKETS = {"voice-notes", "messages", "documents"}


def run():
    print("=" * 60)
    print("PHASE 88 — ENSURE SUPABASE BUCKETS")
    print("=" * 60)

    try:
        sb = get_supabase_admin()
    except Exception as e:
        print(f"  FAIL supabase client: {e}")
        return False

    # List existing buckets
    try:
        resp = sb.storage.list_buckets()
    except Exception as e:
        print(f"  FAIL listing buckets: {e}")
        return False

    existing = set()
    for b in (resp or []):
        if isinstance(b, dict):
            existing.add(b.get("name") or b.get("id"))
        else:
            existing.add(getattr(b, "name", None) or getattr(b, "id", None) or str(b))
    existing.discard(None)

    print(f"\n  Existing buckets ({len(existing)}): {sorted(existing) if existing else 'none'}")

    missing = [b for b in REQUIRED_BUCKETS if b not in existing]
    present = [b for b in REQUIRED_BUCKETS if b in existing]

    if present:
        print(f"\n  Already present ({len(present)}):")
        for b in present:
            vis = "public" if b in PUBLIC_BUCKETS else "private"
            print(f"    OK  {b} ({vis})")

    if not missing:
        print("\n  All required buckets already exist.")
        print("\n" + "=" * 60)
        print("PHASE 88: PASS (all buckets present)")
        print("=" * 60)
        return True

    print(f"\n  Creating missing buckets ({len(missing)}):")
    created = []
    errors = []
    for bucket in missing:
        try:
            is_public = bucket in PUBLIC_BUCKETS
            sb.storage.create_bucket(bucket, options={"public": is_public})
            vis = "public" if is_public else "private"
            print(f"    OK  {bucket} ({vis})")
            created.append(bucket)
        except Exception as e:
            err = str(e)[:100]
            print(f"    FAIL {bucket}: {err}")
            errors.append({"bucket": bucket, "error": err})

    if errors:
        print(f"\n  {len(errors)} bucket(s) failed to create.")
        print("\n" + "=" * 60)
        print("PHASE 88: FAIL")
        print("=" * 60)
        return False

    print(f"\n  Created {len(created)} bucket(s) successfully.")
    print("\n" + "=" * 60)
    print("PHASE 88: PASS (all buckets present)")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
