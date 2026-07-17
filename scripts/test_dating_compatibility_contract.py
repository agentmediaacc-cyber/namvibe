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
    compat = read("services/dating_compatibility_service.py")
    check("canonical compatibility service exists", "def score_compatibility" in compat)
    check("compatibility is deterministic", "random" not in compat.lower())
    check("compatibility uses real data", "_age(" in compat and "_city(" in compat)
    check("compatibility returns reasons", '"reasons"' in compat)
    check("compatibility returns confidence", '"confidence"' in compat)
    check("compatibility avoids hash()", "hash(" not in compat)
    check("compatibility avoids sensitive signals", "ethnicity" not in compat.lower())
    check("compatibility avoids exact religion hard ranking", "religion" not in compat.lower())


if __name__ == "__main__":
    main()
