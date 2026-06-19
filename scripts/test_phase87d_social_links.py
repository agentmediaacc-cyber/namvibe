"""Phase 87D — Social Link Audit.

Fails if user-facing files contain old /friends, /followers, /following links.
"""

import sys, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_DIRS = {"backups", "__pycache__", ".git", "venv", "node_modules", ".opencode"}
EXCLUDE_FILES = {
    "friend_routes.py",  # legacy compatibility API
}

# Patterns to flag: user-facing href="/friends" or action="/friends" etc.
# We match the bare path (not /messages/api/friends or /social/friends)
PATTERNS = [
    re.compile(r'href="/friends(?:/|")'),
    re.compile(r'href="/followers(?:/|")'),
    re.compile(r'href="/following(?:/|")'),
    re.compile(r'action="/friends(?:/|")'),
    re.compile(r'action="/followers(?:/|")'),
    re.compile(r'action="/following(?:/|")'),
]

# Inline JavaScript redirects like window.location.href = '/friends';
JS_REDIRECT = re.compile(r"""location\.href\s*=\s*['"]/(?:friends|followers|following)(?:/|['"])""")


def run():
    print("=" * 60)
    print("PHASE 87D — SOCIAL LINK AUDIT")
    print("=" * 60)
    failed = 0
    checked = 0

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        # Skip scripts/ dir entirely
        if "scripts" in dirpath.split(os.sep):
            continue
        for fn in filenames:
            if fn in EXCLUDE_FILES:
                continue
            ext = os.path.splitext(fn)[1]
            if ext not in (".html", ".js", ".py"):
                continue
            fpath = os.path.join(dirpath, fn)
            rel = os.path.relpath(fpath, ROOT)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        for pat in PATTERNS:
                            if pat.search(line):
                                print(f"  FAIL {rel}:{lineno} {line.strip()[:80]}")
                                failed += 1
                        if JS_REDIRECT.search(line):
                            print(f"  FAIL {rel}:{lineno} {line.strip()[:80]}")
                            failed += 1
                checked += 1
            except Exception as e:
                print(f"  WARN {rel}: {e}")

    print(f"\n  Checked {checked} files, found {failed} old social link(s)")
    print("=" * 60)
    if failed:
        print("PHASE 87D: FAIL")
        print("=" * 60)
        return False
    print("PHASE 87D: PASS")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
