#!/usr/bin/env python3
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check(label, ok, details=""):
    status = "PASS" if ok else "FAIL"
    suffix = f" - {details}" if details else ""
    print(f"{status}: {label}{suffix}")
    return ok


def main():
    failures = 0

    base = read("templates/base.html")
    chain_home = read("static/js/chain_home.js")
    migration_path = ROOT / "scripts" / "fix_phase61_profile_schema_csrf.py"
    migration = migration_path.read_text(encoding="utf-8") if migration_path.exists() else ""
    homepage = read("services/homepage_service.py")
    profile = read("services/profile_service.py")
    neon = read("services/neon_service.py")

    checks = [
        check("csrf meta tag exists", '<meta name="csrf-token" content="{{ csrf_token() }}">' in base),
        check("fetch helper sends X-CSRFToken", "X-CSRFToken" in chain_home and "chainCsrfHeaders" in chain_home),
        check("base patches same-origin unsafe fetches", "window.fetch = function" in base and "X-CSRFToken" in base),
        check("base injects csrf_token into unsafe forms", 'input.name = "csrf_token"' in base),
        check("migration script exists", migration_path.exists()),
        check("cover_path added in migration", '("cover_path", "TEXT")' in migration),
        check("migration uses only add column if not exists", "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS" in migration),
        check("no SQL text + text pattern remains", not re.search(r"COALESCE\([^)]*'[^)]*\)\s*\+\s*COALESCE|COALESCE\([^)]*\)\s*\+\s*COALESCE\([^)]*'[^)]*\)", homepage)),
        check("profile insert columns include cover_path", '"cover_path"' in profile and '"cover_path"' in neon),
        check("profile insert columns include phase61 schema fields", all(f'"{col}"' in profile or f'"{col}"' in neon for col in ("cover_path", "country", "current_country", "visibility", "profile_type", "posts_count"))),
    ]

    for py_path in [
        ROOT / "scripts" / "fix_phase61_profile_schema_csrf.py",
        ROOT / "scripts" / "audit_phase61_csrf_schema_fix.py",
        ROOT / "services" / "homepage_service.py",
        ROOT / "services" / "profile_service.py",
        ROOT / "services" / "neon_service.py",
    ]:
        try:
            py_compile.compile(str(py_path), doraise=True)
            checks.append(check(f"compile passes for {py_path.relative_to(ROOT)}", True))
        except Exception as exc:
            checks.append(check(f"compile passes for {py_path.relative_to(ROOT)}", False, str(exc)))

    failures = sum(1 for ok in checks if not ok)
    if failures:
        print(f"FAIL: phase61 audit found {failures} issue(s)")
        return 1
    print("PASS: phase61 csrf/schema audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
