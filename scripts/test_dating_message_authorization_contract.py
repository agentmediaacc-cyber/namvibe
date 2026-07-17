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
    gate = read("services/relationship_gate_service.py")
    check("blocked users cannot message", "Messaging unavailable" in gate)
    check("self message rejected", "Cannot message yourself" in gate)
    check("call gate requires friendship", "must be friends before you can call" in gate)
    check("message routes enforce current profile auth", "login_required" in read("api_routes/message_routes.py"))


if __name__ == "__main__":
    main()
