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

from services import creator_feature_service as c  # noqa: E402


def main():
    creator = str(uuid.uuid4())
    supporter = str(uuid.uuid4())
    assert c.creator_dashboard(creator)["earnings"]["total"] == 0
    assert c.create_subscription(creator, supporter, "gold", 100)["ok"]
    assert c.create_paid_post(creator, "Paid", 50)["ok"]
    assert c.create_premium_content(creator, "video", lock_type="paid", price_coins=75)["ok"]
    assert c.request_payout(creator, 500, "bank")["ok"]
    assert c.record_gift_conversion(creator, supporter, coins=30)["ok"]
    assert c.create_revenue_report(creator, "2026-06", 1000, 800)["ok"]
    assert c.create_sponsorship(creator, "Brand", 250)["ok"]
    assert c.award_creator_badge(creator, "rising", "Rising")["ok"]
    assert c.award_supporter_badge(creator, supporter, "top_supporter", "Top Supporter")["ok"]
    assert c.upsert_top_fan(creator, supporter, 99, 1)["ok"]
    assert c.upsert_creator_ranking(creator, "overall", 100, 1)["ok"]
    assert c.request_verification(creator)["ok"]
    print("phase30 creator economy: ok")


if __name__ == "__main__":
    main()
