#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import CONTEXT_PATH, TEST_GROUP_PREFIX, TEST_PREFIX, get_credentials, has_credentials, load_context, login, make_session, print_header, request_json, Results

R = Results()
print_header("PHASE 134 - CLEANUP TEST DATA")
parser = argparse.ArgumentParser()
parser.add_argument("--confirm", action="store_true", help="perform cleanup; default is dry run")
args = parser.parse_args()

context = load_context()
print(f"  [INFO] mode: {'CONFIRMED CLEANUP' if args.confirm else 'DRY RUN'}")
print(f"  [INFO] test prefix: {TEST_PREFIX}")

if not args.confirm:
    R.ok("dry run only; no production data modified")
else:
    if not has_credentials():
        R.warn("credentials missing; endpoint cleanup skipped")
    else:
        creds = get_credentials()
        s = make_session()
        login(s, creds["user_a"])
        thread_id = context.get("thread_id") or os.environ.get("NAMVIBE_TEST_THREAD_ID")
        if thread_id:
            R.warn("message cleanup is endpoint-limited; only explicit PHASE134 ids in context would be removed")
        else:
            R.warn("no thread id in context; message cleanup skipped")

tmp_dir = Path(__file__).resolve().parents[1] / "tmp"
targets = [
    tmp_dir / "phase134_test_image.png",
    tmp_dir / "phase134_test.pdf",
    tmp_dir / "phase134_test_video.webm",
    tmp_dir / "phase134_voice_note.wav",
    CONTEXT_PATH,
]
for target in targets:
    if target.exists():
        if args.confirm:
            target.unlink()
            R.ok(f"removed {target.relative_to(Path(__file__).resolve().parents[1])}")
        else:
            R.ok(f"would remove {target.relative_to(Path(__file__).resolve().parents[1])}")

if args.confirm:
    R.warn("direct DB cleanup intentionally not implemented; use only PHASE134_TEST_ rows if manual cleanup is needed")
else:
    R.warn("run with --confirm to remove local tmp Phase134 files")

R.summary("PHASE 134 - CLEANUP TEST DATA")

