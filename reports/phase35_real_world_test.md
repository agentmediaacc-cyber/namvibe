# CHAIN Phase 35 — Real-World Manual Testing Checklist
Generated: 2026-06-06 11:52:59 UTC

**Instructions:** Test each item on two devices/browsers simultaneously.
Mark [x] for pass, [ ] for fail, N/A for not applicable.

| # | Test | Status (A) | Status (B) | Notes |
|---|------|-----------|-----------|-------|
| 1 | **User A register/login**<br><sub>Register new account A. Log in. Confirm session cookie set.</sub> | [ ] | [ ] | |
| 2 | **User B register/login**<br><sub>Register new account B. Log in from separate browser/incognito.</sub> | [ ] | [ ] | |
| 3 | **User A follows User B**<br><sub>Search User B, tap Follow. Check follower count updates.</sub> | [ ] | [ ] | |
| 4 | **User A sends message to User B**<br><sub>Open DM thread, type message, send.</sub> | [ ] | [ ] | |
| 5 | **User B receives message without refresh**<br><sub>User B's inbox shows new message in real time.</sub> | [ ] | [ ] | |
| 6 | **User B refreshes and message persists**<br><sub>After refresh, message still visible in thread.</sub> | [ ] | [ ] | |
| 7 | **Seen receipt updates**<br><sub>User B opens thread. User A sees 'seen' indicator.</sub> | [ ] | [ ] | |
| 8 | **Typing indicator works**<br><sub>User B types. User A sees 'typing...' in real time.</sub> | [ ] | [ ] | |
| 9 | **Voice note records, uploads, refreshes, plays**<br><sub>Record voice note, send, refresh, play back.</sub> | [ ] | [ ] | |
| 10 | **Image/document attachment uploads and persists**<br><sub>Attach image/doc, send, refresh, confirm visible.</sub> | [ ] | [ ] | |
| 11 | **Audio call A -> B**<br><sub>User A initiates audio call to B. B receives.</sub> | [ ] | [ ] | |
| 12 | **Video call A -> B**<br><sub>User A initiates video call to B. B receives.</sub> | [ ] | [ ] | |
| 13 | **Incoming ringtone plays**<br><sub>B receives call — audio plays.</sub> | [ ] | [ ] | |
| 14 | **Outgoing ringback plays**<br><sub>A hears ringback while calling B.</sub> | [ ] | [ ] | |
| 15 | **Missed call recorded**<br><sub>B does not answer. A sees missed call in recent calls.</sub> | [ ] | [ ] | |
| 16 | **Recent call log persists**<br><sub>Both A and B see the call in /calls/recent after refresh.</sub> | [ ] | [ ] | |
| 17 | **Call duration saved**<br><sub>After answered call ends, duration appears in log.</sub> | [ ] | [ ] | |
| 18 | **Busy-user protection works**<br><sub>B is on another call. A sees 'busy' or gets voicemail.</sub> | [ ] | [ ] | |
| 19 | **Group creation**<br><sub>A creates a group. Group appears in A's group list.</sub> | [ ] | [ ] | |
| 20 | **Public group join**<br><sub>B finds and joins public group. B sees group messages.</sub> | [ ] | [ ] | |
| 21 | **Private group request**<br><sub>A creates private group. B requests join. A approves.</sub> | [ ] | [ ] | |
| 22 | **Group message**<br><sub>A sends message in group. All members see it.</sub> | [ ] | [ ] | |
| 23 | **Group call**<br><sub>A starts group call. B joins.</sub> | [ ] | [ ] | |
| 24 | **Story/status upload**<br><sub>A uploads a story. B sees it on A's profile.</sub> | [ ] | [ ] | |
| 25 | **Reel upload**<br><sub>A uploads a reel. Reel appears on A's profile.</sub> | [ ] | [ ] | |
| 26 | **Post creation**<br><sub>A creates a text/image post. Post appears on profile.</sub> | [ ] | [ ] | |
| 27 | **Live start**<br><sub>A starts a live stream. Stream listed on /live/.</sub> | [ ] | [ ] | |
| 28 | **Live appears on homepage/live page**<br><sub>A's live appears on / and /live/ for B.</sub> | [ ] | [ ] | |
| 29 | **User B joins live**<br><sub>B clicks on A's live room. B sees video/comments.</sub> | [ ] | [ ] | |
| 30 | **Live comment**<br><sub>B types a comment. A sees it in real time.</sub> | [ ] | [ ] | |
| 31 | **Viewer count updates**<br><sub>Viewer count increments when B joins.</sub> | [ ] | [ ] | |
| 32 | **Gift/live wallet action**<br><sub>B sends gift during live. A's wallet reflects.</sub> | [ ] | [ ] | |
| 33 | **Push notification permission**<br><sub>Browser prompts for notification permission. A allows.</sub> | [ ] | [ ] | |
| 34 | **Message push notification**<br><sub>B sends message to A while A is on different tab. Push fires.</sub> | [ ] | [ ] | |
| 35 | **Incoming call push notification**<br><sub>B calls A while A is on different tab. Push fires.</sub> | [ ] | [ ] | |
| 36 | **Missed call push notification**<br><sub>B calls A. A doesn't answer. Missed call push fires.</sub> | [ ] | [ ] | |
| 37 | **Wallet page loads**<br><sub>/wallet loads and shows balance/history.</sub> | [ ] | [ ] | |
| 38 | **Creator dashboard loads**<br><sub>/creator/dashboard loads with stats/tabs.</sub> | [ ] | [ ] | |
| 39 | **Creator subscription/premium content persists**<br><sub>Create subscription. Verify it persists after refresh.</sub> | [ ] | [ ] | |
| 40 | **Dating page loads and safety settings apply**<br><sub>/dating loads. Safety settings toggle works.</sub> | [ ] | [ ] | |
| 41 | **Safety report submits**<br><sub>Submit safety report. Confirmation shown.</sub> | [ ] | [ ] | |
| 42 | **Block/unblock user**<br><sub>A blocks B. B cannot see A's profile/messages. Unblock restores.</sub> | [ ] | [ ] | |
| 43 | **Notifications center updates**<br><sub>Notification count updates on bell icon. List reflects new items.</sub> | [ ] | [ ] | |
| 44 | **Logout/login persistence**<br><sub>A logs out, logs in. Profile, messages, calls, wallet data intact.</sub> | [ ] | [ ] | |
| 45 | **Mobile screen works**<br><sub>All pages render without horizontal scroll on 375px viewport.</sub> | [ ] | [ ] | |
| 46 | **Laptop screen works**<br><sub>All pages render correctly on 1440px viewport.</sub> | [ ] | [ ] | |
| 47 | **Slow network behavior**<br><sub>Throttle to 'Slow 3G' in dev tools. Pages load gracefully.</sub> | [ ] | [ ] | |
| 48 | **Offline/reconnect behavior**<br><sub>Go offline. Reconnect. Socket reconnects. Messages sync.</sub> | [ ] | [ ] | |
| 49 | **Browser console — no critical JS errors**<br><sub>Open devtools console. No uncaught errors on any page.</sub> | [ ] | [ ] | |
| 50 | **Server logs — no 500 errors**<br><sub>Check server logs. No 500 Internal Server Error during flows.</sub> | [ ] | [ ] | |

## Summary
- Passed: ___ / 50
- Failed: ___
- N/A: ___

## Blockers Found
1. ...

## Verdict
- [ ] Launch-ready (all pass)
- [ ] Blocked (see blockers above)

_This checklist must be completed before public launch._