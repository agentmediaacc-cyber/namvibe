#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish_namvibe_promo_reel.py"


def _prepare_assets(root: Path) -> Path:
    media = root / "static" / "uploads" / "reels" / "namvibe_promo"
    media.mkdir(parents=True, exist_ok=True)
    for name, content in {
        "namvibe_promo_master.mp4": b"master",
        "namvibe_promo_web.mp4": b"web",
        "namvibe_promo_thumbnail.jpg": b"thumb",
        "namvibe_promo_poster.jpg": b"poster",
        "namvibe_promo_captions.vtt": b"WEBVTT\n",
        "namvibe_promo_manifest.json": json.dumps({"duration_seconds": 55, "title": "x"}),
    }.items():
        (media / name).write_bytes(content if isinstance(content, bytes) else content.encode())
    return media


def _last_json(text: str) -> dict:
    for raw in reversed([line.strip() for line in text.splitlines() if line.strip()]):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    raise AssertionError("no JSON payload found")


def main() -> int:
    with tempfile.TemporaryDirectory(dir=ROOT) as td:
        temp = Path(td)
        media = _prepare_assets(Path(td))
        fake_pkg = temp / "fakepkg"
        (fake_pkg / "services").mkdir(parents=True, exist_ok=True)
        (fake_pkg / "services" / "__init__.py").write_text("", encoding="utf-8")
        (fake_pkg / "services" / "neon_service.py").write_text(
            "def fetch_one(*args, **kwargs):\n    return {'database_name': 'neondb', 'reels_table': 'chain_reels', 'reel_count': 67}\n"
            "def fast_query(*args, **kwargs):\n    sql = args[0].lower() if args else ''\n    if 'from chain_profiles' in sql:\n        return [{'id': 'creator-1', 'username': 'namvibe', 'display_name': 'NamVibe Official'}]\n    if 'from chain_reels' in sql:\n        return [{'id': 'promo-reel-1', 'visibility': 'public', 'processing_status': 'ready', 'deleted_at': None, 'views_count': 0, 'likes_count': 0, 'comments_count': 0, 'shares_count': 0}]\n    return []\n"
            "def write_query(*args, **kwargs):\n    return []\n"
            "def get_table_columns(*args, **kwargs):\n    if args and args[0] == 'chain_profiles':\n        return ['id','auth_user_id','username','display_name','full_name','profile_type','creator_category','account_type','is_creator','is_verified','verified','email','avatar_url','profile_visibility','visibility','is_public','created_at','updated_at']\n    return ['id','profile_id','caption','video_url','media_url','thumbnail_url','poster_url','storage_bucket','storage_path','media_bucket','media_path','music_title','status','visibility','processing_status','mime_type','file_size','size_bytes','views_count','likes_count','comments_count','shares_count','created_at','updated_at','deleted_at']\n"
            "def table_exists(*args, **kwargs):\n    return True\n",
            encoding="utf-8",
        )
        (fake_pkg / "services" / "media_pipeline.py").write_text(
            "def ffprobe_available():\n    return True\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{fake_pkg}:{ROOT}"
        import importlib.util

        spec = importlib.util.spec_from_file_location("promo_publisher", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        json_safe = module._json_safe
        safe_value = json_safe({
            "decimal_int": Decimal("67"),
            "decimal_precise": Decimal("12.50"),
            "when": datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
            "date": date(2026, 7, 15),
            "uuid": UUID("9f2f6b59-70ec-5870-9595-eaab42c354c1"),
            "path": media / "namvibe_promo_web.mp4",
            "bytes": b"abc",
            "memory": memoryview(b"xyz"),
            "nested": [{"value": Decimal("1")}],
        })
        assert safe_value["decimal_int"] == 67
        assert safe_value["decimal_precise"] == "12.50"
        assert safe_value["when"] == "2026-07-15T12:30:00+00:00"
        assert safe_value["date"] == "2026-07-15"
        assert safe_value["uuid"] == "9f2f6b59-70ec-5870-9595-eaab42c354c1"
        assert safe_value["path"].endswith("namvibe_promo_web.mp4")
        assert safe_value["bytes"] == "616263"
        assert safe_value["memory"] == "78797a"
        assert safe_value["nested"][0]["value"] == 1

        rollback_path = media / "namvibe_promo.rollback.json"
        payload = {
            "existing_profile": {"id": UUID("db2080ad-549b-41ab-a103-fc6938cc4c57"), "created_at": datetime(2026, 7, 15, tzinfo=timezone.utc)},
            "existing_reel": {"file_size": Decimal("67"), "updated_at": datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)},
            "planned_profile": {"id": UUID("db2080ad-549b-41ab-a103-fc6938cc4c57")},
            "planned_reel": {"size_bytes": Decimal("12.50"), "paths": [media / "namvibe_promo_web.mp4"]},
        }
        with patch.object(module, "_rollback_manifest_path", return_value=rollback_path):
            written = module._write_rollback_manifest(media, payload["existing_profile"], payload["existing_reel"], payload["planned_reel"], payload["planned_profile"])
        assert written == rollback_path
        decoded = json.loads(rollback_path.read_text(encoding="utf-8"))
        assert decoded["existing_profile"]["id"] == "db2080ad-549b-41ab-a103-fc6938cc4c57"
        assert decoded["existing_reel"]["file_size"] == 67
        assert decoded["planned_reel"]["size_bytes"] == "12.50"

        temp_target = media / "rollback_failure.json"
        with patch.object(module, "_rollback_manifest_path", return_value=temp_target), patch.object(Path, "replace", side_effect=RuntimeError("boom")):
            try:
                module._write_rollback_manifest(media, None, None, {"id": "x"}, None)
            except RuntimeError:
                pass
        assert not temp_target.with_suffix(temp_target.suffix + ".tmp").exists()
        rollback_path.unlink()
        # Dry-run should print plan without touching the database.
        dry = subprocess.run(
            ["python3", str(SCRIPT), "--dry-run", "--output-dir", str(media)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert dry.returncode == 0, dry.stderr
        payload = _last_json(dry.stdout)
        assert payload["ok"] is True
        assert payload["action"] in {"insert", "update"}
        assert payload["expected_public_url"].startswith("/reels/")
        for name in ("namvibe_promo_master.mp4", "namvibe_promo_web.mp4", "namvibe_promo_thumbnail.jpg", "namvibe_promo_poster.jpg", "namvibe_promo_manifest.json"):
            assert (media / name).exists()
        for child in media.iterdir():
            child.unlink()
        media.rmdir()
        print("TEST_OK promo reel publisher")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
