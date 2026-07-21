#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {label}" + (f" -- {detail}" if detail and not ok else ""))
    return ok


def main() -> int:
    from services.gallery_service import get_profile_gallery

    rows = [
        {"id": "1", "profile_id": "p1", "media_type": "image", "public_url": "/static/uploads/a.jpg", "visibility": "public", "created_at": "2026-07-21T00:00:00+00:00"},
        {"id": "2", "profile_id": "p1", "media_type": "image", "public_url": "/static/uploads/b.jpg", "visibility": "public", "created_at": "2026-07-20T00:00:00+00:00"},
    ]

    def fake_fast_query(sql, params=None, timeout_ms=None, default=None):
        if "COUNT(*)" in sql:
            return [{"count": len(rows)}]
        return rows

    import services.gallery_service as gs
    real_fast_query = gs.fast_query
    gs.fast_query = fake_fast_query
    try:
        items, total = get_profile_gallery("p1", viewer_id="viewer", page=1, per_page=20)
    finally:
        gs.fast_query = real_fast_query

    ok = True
    ok &= check("gallery returns items", len(items) == 2, str(items))
    ok &= check("gallery returns count", total == 2, str(total))
    ok &= check("gallery keeps public urls", all(item.get("public_url") for item in items), str(items))
    ok &= check("gallery normalizes media_url", all(item.get("media_url") for item in items), str(items))
    print("TEST_OK profile gallery media contract" if ok else "TEST_FAIL profile gallery media contract")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
