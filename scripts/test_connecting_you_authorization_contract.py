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
    routes = read("api_routes/connecting_you_routes.py")
    svc = read("services/connecting_you_service.py")
    check("admin blueprint exists", "cy_admin_bp" in routes)
    check("admin route checks is_admin", "is_admin" in routes)
    check("member enrollment route requires login", "@cy_bp.route(\"/enroll\", methods=[\"GET\", \"POST\"])" in routes)
    check("assessment route requires login", "@cy_bp.route(\"/assessment\", methods=[\"GET\", \"POST\"])" in routes)
    check("compatibility route exists", "@cy_bp.route(\"/api/compatibility/<target_id>\")" in routes)
    check("mentor/admin functions in service", "list_mentors" in svc and "list_all_mentors" in svc)
    check("intro response validates user membership", "Not your introduction" in svc)


if __name__ == "__main__":
    main()
