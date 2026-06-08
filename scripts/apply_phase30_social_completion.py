#!/usr/bin/env python3
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])

sys.path.insert(0, str(ROOT))

from services.neon_service import write_query  # noqa: E402


def _statements(sql):
    chunks = []
    current = []
    in_single = False
    for char in sql:
        if char == "'":
            in_single = not in_single
        if char == ";" and not in_single:
            statement = "".join(current).strip()
            if statement:
                chunks.append(statement)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        chunks.append(tail)
    return chunks


def main():
    path = ROOT / "sql" / "phase30_social_completion.sql"
    sql = "\n".join(
        line for line in path.read_text().splitlines()
        if not line.lstrip().startswith("--")
    )
    applied = 0
    for statement in _statements(sql):
        if not statement:
            continue
        write_query(statement, timeout_ms=12000)
        applied += 1
    print(f"phase30 social completion migration applied: {applied} statement(s)")


if __name__ == "__main__":
    main()
