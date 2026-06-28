#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.storage_health_service import check_supabase_storage
from utils.supabase_client import get_supabase_admin

PUBLIC_BUCKETS = set()


def required_bucket_creates(existing):
    profile_routes = (ROOT / "api_routes" / "profile_routes.py").read_text()
    storage_service = (ROOT / "services" / "storage_service.py").read_text()
    verification_engine = (ROOT / "services" / "verification_engine.py").read_text()
    verification_required = (
        "upload_verification_file" in profile_routes
        or "chain-verification" in verification_engine
        or "chain-verification" in storage_service
    )

    if not verification_required:
        return []
    return [] if "chain-verification" in existing else ["chain-verification"]


def main():
    health = check_supabase_storage()
    existing = set(health.get("existing_buckets") or [])
    missing = required_bucket_creates(existing)
    if not missing:
        print("PASS")
        print("No missing required buckets.")
        return 0

    create_enabled = os.environ.get("CREATE_MISSING_BUCKETS") == "1"
    if not create_enabled:
        print("DRY-RUN")
        for bucket_name in missing:
            print(bucket_name)
        return 0

    admin = get_supabase_admin()
    created = []
    failed = []
    for bucket_name in missing:
        try:
            admin.storage.create_bucket(bucket_name, options={"public": bucket_name in PUBLIC_BUCKETS})
            created.append(bucket_name)
        except Exception as error:
            failed.append((bucket_name, str(error)))

    if failed:
        print("FAIL")
        for bucket_name, _ in failed:
            print(bucket_name)
        return 1

    print("PASS")
    for bucket_name in created:
        print(bucket_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
