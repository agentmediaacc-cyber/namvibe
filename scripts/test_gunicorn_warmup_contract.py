#!/usr/bin/env python3
"""Contracts for the Gunicorn post-worker warmup hook."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CONF_PATH = ROOT / "gunicorn.conf.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_conf():
    spec = importlib.util.spec_from_file_location("gunicorn_conf_for_test", CONF_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load gunicorn.conf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(name: str, condition: bool, detail: object = "") -> None:
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def main() -> None:
    conf = load_conf()

    # The hook must be a no-op when prewarm is explicitly disabled.
    os.environ["CHAIN_DISABLE_PREWARM"] = "1"
    called = []
    with patch("threading.Thread", side_effect=AssertionError("thread must not be created")):
        conf.post_worker_init(SimpleNamespace(log=SimpleNamespace(warning=lambda *a, **k: called.append((a, k)))))
    check("disabled prewarm skips thread creation", called == [], called)

    # With prewarm enabled, the hook should only schedule background work.
    os.environ.pop("CHAIN_DISABLE_PREWARM", None)
    created = []
    background_calls = []

    class FakeThread:
        def __init__(self, *, target=None, daemon=None):
            created.append({"target": target, "daemon": daemon})
            self.target = target
            self.daemon = daemon

        def start(self):
            background_calls.append("started")

    worker = SimpleNamespace(log=SimpleNamespace(warning=lambda *a, **k: None))
    with patch("threading.Thread", side_effect=lambda *a, **k: FakeThread(*a, **k)), \
         patch("services.neon_service._pool_instance", side_effect=AssertionError("pool warmup must not run synchronously")), \
         patch("services.reels_service.get_reel_feed", side_effect=AssertionError("feed warmup must not run synchronously")), \
         patch("services.reels_service.get_reel_comments_page", side_effect=AssertionError("comment warmup must not run synchronously")), \
         patch("services.homepage_warmup_service.warm_homepage_cache", side_effect=AssertionError("homepage warmup must not run synchronously")), \
         patch("time.sleep", side_effect=AssertionError("sleep must not run synchronously")):
        conf.post_worker_init(worker)

    check("prewarm schedules one daemon thread", len(created) == 1 and created[0]["daemon"] is True, created)
    check("prewarm thread is started", background_calls == ["started"], background_calls)

    print("TEST_OK gunicorn warmup contract")


if __name__ == "__main__":
    main()
