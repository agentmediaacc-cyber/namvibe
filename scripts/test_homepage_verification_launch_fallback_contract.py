#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCH_SCRIPT = ROOT / "scripts" / "launch_release_host_verification_macos.sh"
RUN_SCRIPT = ROOT / "scripts" / "run_release_host_verification.sh"


def main() -> int:
    launch_text = LAUNCH_SCRIPT.read_text(encoding="utf-8")
    run_text = RUN_SCRIPT.read_text(encoding="utf-8")
    launch_required = [
        "DIRECT_FALLBACK",
        "direct_fallback",
        "if [[ \"$DIRECT_FALLBACK\" -eq 1 ]]; then",
        "bootstrap_status",
        "RUN_DIR=\"$RUN_DIR\" bash \"$JOB_WRAPPER\"",
        "SOURCE_ENV_REPO",
        'git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel',
        'if [[ -x "$SOURCE_REPO/venv/bin/python3" ]]; then',
        'SOURCE_VENV="$HOME/Desktop/chain_app/venv"',
        'if [[ ! -f "$SOURCE_ENV_REPO/.env" && -f "$HOME/Desktop/chain_app/.env" ]]; then',
    ]
    run_required = [
        "HOMEPAGE_REPORT_TIMEOUT_SECONDS",
        "timeout_after_seconds=",
        "err.write(f'timeout_after_seconds={timeout_s}\\n'.encode())",
    ]
    missing = [needle for needle in launch_required if needle not in launch_text]
    missing += [needle for needle in run_required if needle not in run_text]
    if missing:
        raise SystemExit(f"missing_contract_tokens: {missing}")
    forbidden = 'SOURCE_REPO="${REPO:-$HOME/Desktop/chain_app}"'
    if forbidden in launch_text:
        raise SystemExit("launcher still defaults source repo to Desktop checkout")
    print("TEST_OK homepage launch fallback contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
