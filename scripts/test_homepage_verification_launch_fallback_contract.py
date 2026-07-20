#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "launch_release_host_verification_macos.sh"


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")
    required = [
        "DIRECT_FALLBACK",
        "direct_fallback",
        "if [[ \"$DIRECT_FALLBACK\" -eq 1 ]]; then",
        "bootstrap_status",
        "RUN_DIR=\"$RUN_DIR\" bash \"$JOB_WRAPPER\"",
        "SOURCE_ENV_REPO",
        'git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel',
        'if [[ -x "$SOURCE_REPO/venv/bin/python3" ]]; then',
        'SOURCE_VENV="$HOME/Desktop/chain_app/venv"',
    ]
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise SystemExit(f"missing_contract_tokens: {missing}")
    forbidden = 'SOURCE_REPO="${REPO:-$HOME/Desktop/chain_app}"'
    if forbidden in text:
        raise SystemExit("launcher still defaults source repo to Desktop checkout")
    print("TEST_OK homepage launch fallback contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
