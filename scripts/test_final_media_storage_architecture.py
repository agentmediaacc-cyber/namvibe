#!/usr/bin/env python3
import ast
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def read(rel):
    path = BASE / rel
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}" + (f" - {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"FAIL {name}" + (f" - {detail}" if detail else ""))


def route_source_has(rel, *patterns):
    text = read(rel)
    return all(pattern in text for pattern in patterns)


def main():
    os.chdir(BASE)
    sys.path.insert(0, str(BASE))

    try:
        import services.supabase_storage_router as router
        check("storage router imports cleanly", True)
    except Exception as error:
        check("storage router imports cleanly", False, str(error))
        return 1

    check("Supabase env vars are read", hasattr(router, "SUPABASE_URL") and hasattr(router, "SUPABASE_SERVICE_ROLE_KEY"))
    expected = {
        "avatars": "avatars",
        "covers": "covers",
        "posts": "post-media",
        "reels": "reels",
        "stories": "stories",
        "messages": "message-media",
        "voice_notes": "voice-notes",
        "documents": "documents",
        "live": "live-media",
        "marketplace": "marketplace-media",
    }
    check("bucket mapping is correct", router.BUCKET_MAPPING == expected, str(router.BUCKET_MAPPING))

    sql = read("sql/final_media_storage_metadata.sql").lower()
    check("SQL migration is idempotent", "if not exists" in sql)
    check("large media not stored as bytea/base64/blob", not any(term in sql for term in (" bytea", "base64", " blob", "large object")))
    for col in ("media_url", "media_path", "media_bucket", "mime_type", "size_bytes", "media_type"):
        check(f"Neon metadata column {col}", col in sql)

    router_text = read("services/supabase_storage_router.py")
    check("production blocks local-only uploads", "return None, \"Supabase Storage is not configured; local uploads are disabled.\"" in router_text and "is_production()" in router_text)
    check("local dev fallback requires flag", 'CHAIN_ALLOW_LOCAL_UPLOADS") == "1"' in router_text)

    check("avatar route uses storage router", route_source_has("services/profile_service.py", "services.supabase_storage_router", "upload_avatar"))
    check("cover route uses storage router", route_source_has("services/profile_service.py", "services.supabase_storage_router", "upload_cover"))
    check("message attachment route uses storage router", route_source_has("services/media_storage_service.py", "services.supabase_storage_router", "messages"))
    check("voice note route uses storage router", route_source_has("services/media_storage_service.py", "voice_notes"))
    check("reels route uses storage router", route_source_has("services/content_service.py", "upload_file", '"reel": "reels"'))
    check("stories route uses storage router", route_source_has("services/status_service.py", "upload_story_media"))
    check("marketplace route uses storage router", route_source_has("api_routes/marketplace_routes.py", "upload_marketplace_media") and route_source_has("services/storage_service.py", "upload_marketplace_image"))

    raw_patterns = ("file.save(", ".read()")
    route_files = [
        "api_routes/profile_routes.py",
        "api_routes/message_routes.py",
        "api_routes/reels_routes.py",
        "api_routes/status_routes.py",
        "api_routes/live_routes.py",
        "api_routes/marketplace_routes.py",
    ]
    offenders = []
    for rel in route_files:
        text = read(rel)
        if ".read()" in text:
            offenders.append(rel)
    check("no route stores raw file bytes in DB", not offenders, ", ".join(offenders))

    service_text = "\n".join(read(rel) for rel in ["services/content_service.py", "services/messaging_engine.py", "services/profile_service.py", "services/status_service.py", "services/marketplace_service.py"])
    check("Neon only stores URL/path/metadata", all(term in service_text for term in ("media_url", "media_path", "media_bucket", "mime_type", "size_bytes")))

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
