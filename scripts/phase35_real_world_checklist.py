#!/usr/bin/env python3
"""Phase 35 — Real-World Manual Testing Checklist Generator"""

import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

CHECKS = [
    (1, "User A register/login", "manual", "Register new account A. Log in. Confirm session cookie set."),
    (2, "User B register/login", "manual", "Register new account B. Log in from separate browser/incognito."),
    (3, "User A follows User B", "manual", "Search User B, tap Follow. Check follower count updates."),
    (4, "User A sends message to User B", "manual", "Open DM thread, type message, send."),
    (5, "User B receives message without refresh", "manual", "User B's inbox shows new message in real time."),
    (6, "User B refreshes and message persists", "manual", "After refresh, message still visible in thread."),
    (7, "Seen receipt updates", "manual", "User B opens thread. User A sees 'seen' indicator."),
    (8, "Typing indicator works", "manual", "User B types. User A sees 'typing...' in real time."),
    (9, "Voice note records, uploads, refreshes, plays", "manual", "Record voice note, send, refresh, play back."),
    (10, "Image/document attachment uploads and persists", "manual", "Attach image/doc, send, refresh, confirm visible."),
    (11, "Audio call A -> B", "manual", "User A initiates audio call to B. B receives."),
    (12, "Video call A -> B", "manual", "User A initiates video call to B. B receives."),
    (13, "Incoming ringtone plays", "manual", "B receives call — audio plays."),
    (14, "Outgoing ringback plays", "manual", "A hears ringback while calling B."),
    (15, "Missed call recorded", "manual", "B does not answer. A sees missed call in recent calls."),
    (16, "Recent call log persists", "manual", "Both A and B see the call in /calls/recent after refresh."),
    (17, "Call duration saved", "manual", "After answered call ends, duration appears in log."),
    (18, "Busy-user protection works", "manual", "B is on another call. A sees 'busy' or gets voicemail."),
    (19, "Group creation", "manual", "A creates a group. Group appears in A's group list."),
    (20, "Public group join", "manual", "B finds and joins public group. B sees group messages."),
    (21, "Private group request", "manual", "A creates private group. B requests join. A approves."),
    (22, "Group message", "manual", "A sends message in group. All members see it."),
    (23, "Group call", "manual", "A starts group call. B joins."),
    (24, "Story/status upload", "manual", "A uploads a story. B sees it on A's profile."),
    (25, "Reel upload", "manual", "A uploads a reel. Reel appears on A's profile."),
    (26, "Post creation", "manual", "A creates a text/image post. Post appears on profile."),
    (27, "Live start", "manual", "A starts a live stream. Stream listed on /live/."),
    (28, "Live appears on homepage/live page", "manual", "A's live appears on / and /live/ for B."),
    (29, "User B joins live", "manual", "B clicks on A's live room. B sees video/comments."),
    (30, "Live comment", "manual", "B types a comment. A sees it in real time."),
    (31, "Viewer count updates", "manual", "Viewer count increments when B joins."),
    (32, "Gift/live wallet action", "manual", "B sends gift during live. A's wallet reflects."),
    (33, "Push notification permission", "manual", "Browser prompts for notification permission. A allows."),
    (34, "Message push notification", "manual", "B sends message to A while A is on different tab. Push fires."),
    (35, "Incoming call push notification", "manual", "B calls A while A is on different tab. Push fires."),
    (36, "Missed call push notification", "manual", "B calls A. A doesn't answer. Missed call push fires."),
    (37, "Wallet page loads", "manual", "/wallet loads and shows balance/history."),
    (38, "Creator dashboard loads", "manual", "/creator/dashboard loads with stats/tabs."),
    (39, "Creator subscription/premium content persists", "manual", "Create subscription. Verify it persists after refresh."),
    (40, "Dating page loads and safety settings apply", "manual", "/dating loads. Safety settings toggle works."),
    (41, "Safety report submits", "manual", "Submit safety report. Confirmation shown."),
    (42, "Block/unblock user", "manual", "A blocks B. B cannot see A's profile/messages. Unblock restores."),
    (43, "Notifications center updates", "manual", "Notification count updates on bell icon. List reflects new items."),
    (44, "Logout/login persistence", "manual", "A logs out, logs in. Profile, messages, calls, wallet data intact."),
    (45, "Mobile screen works", "manual", "All pages render without horizontal scroll on 375px viewport."),
    (46, "Laptop screen works", "manual", "All pages render correctly on 1440px viewport."),
    (47, "Slow network behavior", "manual", "Throttle to 'Slow 3G' in dev tools. Pages load gracefully."),
    (48, "Offline/reconnect behavior", "manual", "Go offline. Reconnect. Socket reconnects. Messages sync."),
    (49, "Browser console — no critical JS errors", "manual", "Open devtools console. No uncaught errors on any page."),
    (50, "Server logs — no 500 errors", "manual", "Check server logs. No 500 Internal Server Error during flows."),
]


def generate_report():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# CHAIN Phase 35 — Real-World Manual Testing Checklist",
        f"Generated: {now} UTC",
        "",
        "**Instructions:** Test each item on two devices/browsers simultaneously.",
        "Mark [x] for pass, [ ] for fail, N/A for not applicable.",
        "",
        "| # | Test | Status (A) | Status (B) | Notes |",
        "|---|------|-----------|-----------|-------|",
    ]
    for num, name, kind, desc in CHECKS:
        lines.append(f"| {num} | **{name}**<br><sub>{desc}</sub> | [ ] | [ ] | |")

    lines.extend([
        "",
        "## Summary",
        "- Passed: ___ / 50",
        "- Failed: ___",
        "- N/A: ___",
        "",
        "## Blockers Found",
        "1. ...",
        "",
        "## Verdict",
        "- [ ] Launch-ready (all pass)",
        "- [ ] Blocked (see blockers above)",
        "",
        "_This checklist must be completed before public launch._",
    ])
    return "\n".join(lines)


def main():
    report = generate_report()
    report_path = os.path.join(REPORT_DIR, "phase35_real_world_test.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"[PASS] Real-world checklist written to {report_path}")
    print(f"[INFO] {len(CHECKS)} test items defined")
    print()
    print("Manual Testing Checklist:")
    print("=" * 60)
    for num, name, kind, desc in CHECKS:
        print(f"  {num:2d}. {name}")
    print()
    print(f"See {report_path} for full markdown with note columns.")


if __name__ == "__main__":
    main()
