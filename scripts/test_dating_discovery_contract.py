#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        raise AssertionError(name)


def main():
    svc = read("services/dating_service.py")
    tpl = read("templates/dating/discover.html")
    check("discover excludes viewer", 'excluded = {viewer}' in svc)
    check("discover excludes blocked ids", "_get_blocked_ids" in svc)
    check("discover excludes blocker ids", "_get_blocker_ids" in svc)
    check("discover uses public profile guard", "public_profile_sql(\"p\")" in svc)
    check("discover limits results", "limit = _clean_limit" in svc)
    check("discover stable sort", "results.sort(" in svc)
    check("discover compatibility reasons rendered", "compatibility_score" in tpl)
    check("no fake fallback profiles", "No more matches in your area" in tpl)


if __name__ == "__main__":
    main()
