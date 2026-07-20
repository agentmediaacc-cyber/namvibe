#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_release_host_verification.sh"


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")
    required = [
        'BROWSER_SMOKE_ARTIFACT_DIR="$RUN_DIR/repo/artifacts/browser_smoke"',
        'mkdir -p "$BROWSER_SMOKE_ARTIFACT_DIR"',
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit(f"missing_contract_tokens: {missing}")
    print("TEST_OK homepage artifact dir contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
