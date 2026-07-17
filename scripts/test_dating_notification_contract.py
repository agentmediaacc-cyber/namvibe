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
    check("match notifications persist via direct helper", "_emit_dating_match_notification" in svc)
    check("match notifications use canonical dating link", '"/dating/matches"' in svc)
    check("one-sided like does not notify", 'create_notification(target_id, "💘 New Like"' not in read("services/matching_service.py"))


if __name__ == "__main__":
    main()
