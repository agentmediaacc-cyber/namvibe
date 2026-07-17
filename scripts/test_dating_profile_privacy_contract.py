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
    tpl = read("templates/dating/profile.html")
    svc = read("services/dating_service.py")
    check("no email rendered", "email" not in tpl.lower())
    check("no exact DOB rendered", "date_of_birth" not in tpl.lower())
    check("no internal UUID string rendered explicitly", "internal UUID" not in tpl)
    check("phone hidden logic exists", "_may_see_phone" in svc)
    check("dating profile strips sensitive phone", "pop(\"phone\"" in svc)
    check("profile route uses bundle and dating profile", "get_profile_bundle" in read("api_routes/dating_routes.py"))


if __name__ == "__main__":
    main()
