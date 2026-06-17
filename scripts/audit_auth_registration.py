#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [
    ROOT / "app.py",
    ROOT / "api_routes",
    ROOT / "services",
    ROOT / "templates",
    ROOT / "static" / "js",
]
PHRASES = [
    "email not found",
    "profile required",
    "verification required",
    "must verify",
    "country required",
    "phone required",
    "avatar required",
    "complete profile required",
]
IGNORED_PARTS = {
    "__pycache__",
    ".git",
}
ALLOWED_FILES = {
    "scripts/audit_auth_registration.py",
}


def iter_files():
    for root in SCAN_ROOTS:
        if root.is_file():
            yield root
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORED_PARTS for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".html", ".js"}:
                continue
            yield path


def main():
    failures = []
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in PHRASES:
            if phrase in text:
                failures.append((rel, phrase))

    if failures:
        print("FAIL registration blockers found")
        for rel, phrase in failures:
            print(f"{rel}: {phrase}")
        return 1

    print("PASS no registration blocking phrases found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
