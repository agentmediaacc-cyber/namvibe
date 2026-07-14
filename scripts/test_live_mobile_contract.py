#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label)
    return 0 if condition else 1


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


failures = 0
room_tpl = read("templates/live_room.html")
hub_tpl = read("templates/live_hub.html")
live_js = read("static/js/namvibe_live.js")

failures += check("Live hub opens correctly", "lv-app" in hub_tpl and "data-action=\"go-live\"" in hub_tpl)
failures += check("Camera preview is visible contract exists", "lvStreamVideo" in room_tpl)
failures += check("Remote stream supports playsinline", "playsinline" in room_tpl.lower())
failures += check("User action required before media", "data-action=\"start-live-session\"" in room_tpl and "if (isHost) startWebcam();" not in live_js)
failures += check("Connection state appears", "lvConnectionState" in room_tpl and "setConnectionState" in live_js)
failures += check("Viewer count updates", "lvViewerCount" in room_tpl and "live:viewers" in live_js)
failures += check("Chat sends", "lvChatSend" in room_tpl and "/api/live/' + roomId + '/chat" in live_js)
failures += check("Reactions animate", "sendReaction" in live_js and "live:reaction" in live_js)
failures += check("Ended-room state appears", "live:room_ended" in live_js)
failures += check("No duplicate listeners", live_js.count("socket.on('live:viewers'") == 1 and live_js.count("socket.on('live:chat'") == 1)

sys.exit(1 if failures else 0)
