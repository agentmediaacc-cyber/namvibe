#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env, text=True, capture_output=True, check=False)


def main() -> int:
    namespace = f"test_{uuid.uuid4().hex[:12]}"
    env = os.environ.copy()
    env["CHAIN_REDIS_ALLOW_LOCAL_FALLBACK"] = "1"
    env["REQUIRE_SHARED_CACHE"] = "1"
    env["CHAIN_CACHE_NAMESPACE"] = namespace

    writer = run(
        textwrap.dedent(
            """
            import json
            from services.content_service import get_reels_content_version
            from services.redis_service import redis_manager
            from services.reels_service import get_reel_feed, build_public_reels_feed_cache_key

            version = get_reels_content_version("public")
            payload = get_reel_feed(limit=5, cursor=None, viewer_id=None)
            key = build_public_reels_feed_cache_key(content_version=version, limit=5, cursor="first", feed_type="public")
            cached = redis_manager.get_json_result(key)
            ttl = redis_manager.get_ttl(key)
            print(json.dumps({
                "backend": redis_manager.get_health()["backend"],
                "version": version,
                "key": key,
                "ttl": ttl,
                "items": len(payload.get("items", [])),
                "shared": cached.get("shared"),
                "exists": cached.get("value") is not None,
            }))
            """
        ),
        env,
    )
    if writer.returncode != 0:
        print(writer.stdout)
        print(writer.stderr, file=sys.stderr)
        return writer.returncode
    writer_data = json.loads(writer.stdout.strip().splitlines()[-1])
    if not writer_data["shared"] or not writer_data["exists"] or writer_data["ttl"] <= 0:
        print(f"writer_data={writer_data}")
        return 1

    reader = run(
        textwrap.dedent(
            """
            import json
            from unittest.mock import patch
            from services.content_service import get_reels_content_version
            from services.redis_service import redis_manager
            from services.reels_service import get_reel_feed, build_public_reels_feed_cache_key

            version = get_reels_content_version("public")
            key = build_public_reels_feed_cache_key(content_version=version, limit=5, cursor="first", feed_type="public")
            with patch("services.reels_service.fast_query", side_effect=AssertionError("Neon loader should not run")):
                payload = get_reel_feed(limit=5, cursor=None, viewer_id=None)
            print(json.dumps({
                "backend": redis_manager.get_health()["backend"],
                "version": version,
                "key": key,
                "ttl": redis_manager.get_ttl(key),
                "items": len(payload.get("items", [])),
                "exists": redis_manager.get_json_result(key).get("value") is not None,
            }))
            """
        ),
        env,
    )
    if reader.returncode != 0:
        print(reader.stdout)
        print(reader.stderr, file=sys.stderr)
        return reader.returncode
    reader_data = json.loads(reader.stdout.strip().splitlines()[-1])

    assert reader_data["backend"] in {"redis_remote", "redis_local"}
    assert reader_data["version"] == writer_data["version"]
    assert reader_data["key"] == writer_data["key"]
    assert reader_data["exists"] is True
    assert reader_data["ttl"] > 0
    assert reader_data["items"] == writer_data["items"]

    cleanup = run(
        textwrap.dedent(
            """
            from services.content_service import get_reels_content_version
            from services.redis_service import redis_manager
            from services.reels_service import build_public_reels_feed_cache_key

            version = get_reels_content_version("public")
            key = build_public_reels_feed_cache_key(content_version=version, limit=5, cursor="first", feed_type="public")
            redis_manager.delete(key)
            print("CLEANUP_OK")
            """
        ),
        env,
    )
    if cleanup.returncode != 0:
        print(cleanup.stdout)
        print(cleanup.stderr, file=sys.stderr)
        return cleanup.returncode

    print(json.dumps({"PASS": True, "namespace": namespace, "key": writer_data["key"], "ttl": reader_data["ttl"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
