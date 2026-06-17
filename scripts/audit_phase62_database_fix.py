#!/usr/bin/env python3
import os
import re
import sys
import time
import py_compile
import multiprocessing
import queue
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQUIRED_COLUMNS = {
    "cover_path",
    "cover_url",
    "banner_path",
    "banner_url",
    "avatar_storage_path",
    "avatar_storage_bucket",
    "country",
    "current_country",
    "visibility",
    "profile_type",
    "reels_count",
    "saved_count",
    "tagged_count",
}

REQUIRED_INDEXES = {
    "idx_phase62_chain_posts_created_at",
    "idx_phase62_chain_reels_created_at",
    "idx_phase62_chain_profiles_created_at",
    "idx_phase62_chain_stories_created_at",
    "idx_phase62_chain_live_rooms_created_at",
}

TEXT_PLUS_PATTERNS = [
    re.compile(r"COALESCE\([^)]*(?:avatar_url|cover_url|thumbnail_url|bio|location|town)[^)]*\)\s*\+", re.I),
    re.compile(r"\+\s*COALESCE\([^)]*(?:avatar_url|cover_url|thumbnail_url|bio|location|town)[^)]*\)", re.I),
    re.compile(r"COALESCE\([^)]*'[^)]*'\)\s*\+\s*COALESCE\([^)]*'[^)]*'\)", re.I),
]


def check(label, ok, details=""):
    status = "PASS" if ok else "FAIL"
    suffix = f" - {details}" if details else ""
    print(f"{status}: {label}{suffix}")
    return ok


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def _schema_columns(fetch_all):
    rows = fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'chain_profiles'
        """,
        timeout_ms=10000,
    )
    return {row.get("column_name") for row in rows or []}


def _index_names(fetch_all):
    rows = fetch_all(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        """,
        timeout_ms=10000,
    )
    return {row.get("indexname") for row in rows or []}


def _source_text_plus_hits():
    hits = []
    for base in ("services", "api_routes", "scripts"):
        for path in (ROOT / base).rglob("*.py"):
            if "secrets" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in TEXT_PLUS_PATTERNS:
                if pattern.search(text):
                    hits.append(str(path.relative_to(ROOT)))
                    break
    return sorted(set(hits))


def _warm_homepage_worker(result_queue):
    os.environ.setdefault("CHAIN_FAST_LOCAL", "0")
    from services.homepage_cache_service import invalidate_homepage_cache
    from services.homepage_service import build_homepage_payload

    invalidate_homepage_cache()
    build_homepage_payload()
    started = time.perf_counter()
    build_homepage_payload()
    result_queue.put({"ok": True, "ms": (time.perf_counter() - started) * 1000})


def _warm_homepage_ms(timeout_seconds=20):
    result_queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_warm_homepage_worker, args=(result_queue,))
    proc.start()
    proc.join(timeout_seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(3)
        raise TimeoutError(f"warm homepage audit exceeded {timeout_seconds}s")
    try:
        result = result_queue.get_nowait()
    except queue.Empty:
        if proc.exitcode:
            raise RuntimeError(f"warm homepage audit exited with {proc.exitcode}")
        raise RuntimeError("warm homepage audit produced no result")
    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "warm homepage audit failed")
    return float(result["ms"])


def main():
    os.chdir(ROOT)
    checks = []

    from services.neon_service import fetch_all

    columns = _schema_columns(fetch_all)
    missing_columns = sorted(REQUIRED_COLUMNS - columns)
    checks.append(check("cover_path exists", "cover_path" in columns))
    checks.append(check("all phase62 profile columns exist", not missing_columns, ", ".join(missing_columns)))

    indexes = _index_names(fetch_all)
    missing_indexes = sorted(REQUIRED_INDEXES - indexes)
    checks.append(check("phase62 created_at indexes exist", not missing_indexes, ", ".join(missing_indexes)))

    hits = _source_text_plus_hits()
    checks.append(check("no text + text queries remain", not hits, ", ".join(hits)))

    homepage = read("services/homepage_service.py")
    checks.append(check("homepage uses ThreadPoolExecutor", "ThreadPoolExecutor" in homepage and "_EXECUTOR.submit" in homepage))
    checks.append(check("homepage section TTLs set", 'ttl=60' in homepage and 'ttl=30' in homepage))
    checks.append(check("suggested people uses numeric CASE scoring", "CASE WHEN" in homepage and "NULLIF({col}, '')" not in homepage))

    for py_path in [
        ROOT / "scripts" / "fix_phase62_database_fix.py",
        ROOT / "scripts" / "audit_phase62_database_fix.py",
        ROOT / "services" / "homepage_service.py",
    ]:
        try:
            py_compile.compile(str(py_path), doraise=True)
            checks.append(check(f"compile passes for {py_path.relative_to(ROOT)}", True))
        except Exception as exc:
            checks.append(check(f"compile passes for {py_path.relative_to(ROOT)}", False, str(exc)))

    try:
        warm_ms = _warm_homepage_ms()
        checks.append(check("homepage_total_ms < 1000 on warm cache", warm_ms < 1000, f"{warm_ms:.2f}ms"))
    except Exception as exc:
        checks.append(check("homepage_total_ms < 1000 on warm cache", False, str(exc)))

    failures = sum(1 for ok in checks if not ok)
    if failures:
        print(f"FAIL: phase62 audit found {failures} issue(s)")
        return 1
    print("PASS: phase62 database/performance audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
