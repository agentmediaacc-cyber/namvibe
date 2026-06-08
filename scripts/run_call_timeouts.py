#!/usr/bin/env python3
"""
Phase 40: Call Timeout Checker
Marks ringing calls older than 30 seconds as missed.
Run periodically via cron or scheduler.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()

from services.webrtc_call_service import check_call_timeouts


def run():
    with app.app_context():
        count = check_call_timeouts()
        print(f"[call_timeouts] Checked for stale calls: {count} timed out")
    return count


if __name__ == "__main__":
    run()
