#!/usr/bin/env python3
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))
os.environ["FLASK_TESTING"] = "1"

from services import group_feature_service as g  # noqa: E402


def main():
    owner = str(uuid.uuid4())
    member = str(uuid.uuid4())
    public_group = g.create_group(owner, "Public", "public")
    private_group = g.create_group(owner, "Private", "private")
    paid_group = g.create_group(owner, "Paid", "public", access_type="paid", join_fee=10, paid_access=True)
    premium_group = g.create_group(owner, "Premium", "public", premium_only=True)
    assert public_group["ok"] and private_group["ok"] and paid_group["ok"] and premium_group["ok"]
    group_id = public_group["group"]["id"]
    assert g.join_public_group(group_id, member)["ok"]
    assert g.request_join(private_group["group"]["id"], member)["ok"]
    assert g.invite_link(group_id)["invite_link"]
    assert g.set_role(group_id, member, "moderator", owner)["ok"]
    assert g.create_announcement(group_id, owner, "Update", "Announcement")["ok"]
    assert g.create_advert(group_id, owner, "Advert", "Body")["ok"]
    assert g.record_analytics(group_id, "views", 12)["ok"]
    assert g.request_group_verification(group_id, owner, "verify")["ok"]
    assert g.create_group_post(group_id, owner, "message", "message")["ok"]
    assert g.create_group_live_room(group_id, owner, "Group live")["ok"]
    assert g.create_group_reel(group_id, owner, "Reel")["ok"]
    assert g.create_marketplace_item(group_id, owner, "Item", "Description", 5)["ok"]
    print("phase30 groups advanced: ok")


if __name__ == "__main__":
    main()
