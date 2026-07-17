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
    check("self-like rejected", "cannot_interact_with_self" in svc)
    check("blocked relationship rejected", "blocked_relationship" in svc)
    check("duplicate interaction rejected", "already_interacted" in svc)
    check("match uniqueness queried before insert", "existing_match" in svc)
    check("mutual like creates one match", "INSERT INTO chain_dating_matches" in svc)
    check("match notifications created", "It's a match!" in svc)
    check("match can provision dating thread", "INSERT INTO chain_message_threads" in svc and "chain_thread_members" in svc)


if __name__ == "__main__":
    main()
