#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.media_storage_service import SUPPORTED_BUCKETS
from services.storage_health_service import check_supabase_storage
from utils.supabase_client import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

ACTIVE_UPLOAD_TYPES = {
    "avatars": {"avatars", "chain-avatars"},
    "covers": {"covers", "chain-covers"},
    "posts": {"posts", "chain-posts"},
    "reels": {"reels", "chain-reels"},
    "stories_status": {"stories", "chain-stories", "chain-status"},
    "messages": {"messages", "chain-messages"},
    "documents": {"documents"},
    "voice_notes": {"voice-notes"},
}

OPTIONAL_UPLOAD_TYPES = {
    "verification": {"chain-verification"},
    "live": {"chain-live"},
}


def _line(status, label, detail=""):
    suffix = f" :: {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


def main():
    failures = []
    warnings = []
    allow_create = os.environ.get("CREATE_MISSING_BUCKETS") == "1"
    _line("PASS" if SUPABASE_URL else "FAIL", "SUPABASE_URL configured")
    _line("PASS" if SUPABASE_ANON_KEY else "FAIL", "SUPABASE_ANON_KEY configured")
    _line("PASS" if SUPABASE_SERVICE_ROLE_KEY else "FAIL", "SUPABASE_SERVICE_ROLE_KEY configured")

    health = check_supabase_storage()
    inventory_available = health.get("bucket_count") is not None and not health.get("error")
    if inventory_available:
        _line("PASS", "Supabase storage connection", f"bucket_count={health.get('bucket_count', 0)}")
    else:
        _line("FAIL", "Supabase storage connection", health.get("error") or "unknown_error")
        failures.append("supabase storage not ready")

    existing = set(health.get("existing_buckets") or [])
    verification_required = "upload_verification_file" in (ROOT / "api_routes" / "profile_routes.py").read_text() or "chain-verification" in (ROOT / "services" / "verification_engine.py").read_text()
    if inventory_available:
        for upload_type, acceptable in ACTIVE_UPLOAD_TYPES.items():
            matched = sorted(existing & acceptable)
            if matched:
                _line("PASS", f"{upload_type} bucket available", ", ".join(matched))
            else:
                _line("FAIL", f"{upload_type} bucket available", f"expected one of: {', '.join(sorted(acceptable))}")
                failures.append(f"missing required bucket for {upload_type}: expected one of {', '.join(sorted(acceptable))}")

        for upload_type, acceptable in OPTIONAL_UPLOAD_TYPES.items():
            matched = sorted(existing & acceptable)
            required = upload_type == "verification" and verification_required
            if matched:
                _line("PASS", f"{upload_type} bucket available", ", ".join(matched))
            elif required:
                _line("FAIL", f"{upload_type} bucket available", f"expected one of: {', '.join(sorted(acceptable))}")
                failures.append(f"missing required bucket for {upload_type}: expected one of {', '.join(sorted(acceptable))}")
            else:
                _line("WARN", f"{upload_type} bucket available", f"not required by active config; acceptable: {', '.join(sorted(acceptable))}")
                warnings.append(f"optional bucket missing for {upload_type}")
    else:
        for upload_type in ACTIVE_UPLOAD_TYPES:
            _line("WARN", f"{upload_type} bucket available", "inventory unavailable")
        if verification_required:
            _line("WARN", "verification bucket available", "inventory unavailable; active flow expects chain-verification")
        else:
            _line("WARN", "verification bucket available", "inventory unavailable; verification bucket optional")
        _line("WARN", "live bucket available", "inventory unavailable")
        warnings.append("bucket inventory unavailable")

    storage_service = (ROOT / "services" / "storage_service.py").read_text()
    upload_routes = (ROOT / "api_routes" / "post_routes.py").read_text() + (ROOT / "api_routes" / "message_routes.py").read_text()
    if "router_upload" in storage_service and "supabase_storage_router" in storage_service:
        _line("PASS", "uploads route through Supabase router")
    else:
        _line("FAIL", "uploads route through Supabase router")
        failures.append("storage_service not routed through supabase_storage_router")
    if "upload_media_to_supabase" in upload_routes or "upload_media_file" in upload_routes:
        _line("PASS", "upload endpoints use Supabase-aware services")
    else:
        _line("FAIL", "upload endpoints use Supabase-aware services")
        failures.append("upload endpoints missing supabase-aware service calls")

    if not allow_create:
        _line("PASS", "bucket creation mode", "dry-run only; CREATE_MISSING_BUCKETS!=1")
    else:
        _line("WARN", "bucket creation mode", "CREATE_MISSING_BUCKETS=1 enables create script")

    if failures:
        print("FAIL")
        for failure in failures:
            print(failure)
        return 1
    if warnings:
        print("WARN")
        for warning in warnings:
            print(warning)
        return 0
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
