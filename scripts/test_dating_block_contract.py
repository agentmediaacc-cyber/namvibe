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
    check("block rejects self", "cannot_block_self" in svc)
    check("block checks duplicates", "already_blocked" in svc)
    check("block deletes matches", "DELETE FROM chain_dating_matches" in svc)
    check("block deletes likes", "DELETE FROM chain_dating_likes" in svc)
    check("block API is POST", '@dating_bp.route("/api/block", methods=["POST"])' in read("api_routes/dating_routes.py"))


if __name__ == "__main__":
    main()
