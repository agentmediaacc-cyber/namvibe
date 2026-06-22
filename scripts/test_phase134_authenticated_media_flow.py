#!/usr/bin/env python3
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import TEST_PREFIX, get_credentials, has_credentials, load_context, login, make_session, print_header, request_json, Results, unique_test_id, warn_missing_credentials

R = Results()
print_header("PHASE 134 - AUTHENTICATED MEDIA FLOW")
TMP = Path(__file__).resolve().parents[1] / "tmp"


def make_files():
    TMP.mkdir(exist_ok=True)
    img = TMP / "phase134_test_image.png"
    pdf = TMP / "phase134_test.pdf"
    video = TMP / "phase134_test_video.webm"
    img.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    video.write_bytes(b"\x1a\x45\xdf\xa3PHASE134_TEST_WEBM")
    return img, pdf, video


if not has_credentials():
    warn_missing_credentials(R)
    R.warn("authenticated media flow skipped")
else:
    creds, context = get_credentials(), load_context()
    thread_id = context.get("thread_id") or os.environ.get("NAMVIBE_TEST_THREAD_ID")
    if not thread_id:
        R.warn("missing disposable thread id; media upload skipped")
    else:
        s = make_session()
        login_response = login(s, creds["user_a"])
        if "/auth/login" in login_response.url:
            R.fail("user A login failed")
        else:
            R.ok("user A login")
        img, pdf, video = make_files()
        for path, mime, label in [(img, "image/png", "image"), (pdf, "application/pdf", "PDF"), (video, "video/webm", "video")]:
            with path.open("rb") as handle:
                res, data = request_json(s, "POST", "/messages/api/upload", {"thread_id": thread_id, "body": f"{TEST_PREFIX}{unique_test_id()} {label}"}, {"file": (path.name, handle, mime)})
            if res.status_code >= 500:
                R.fail(f"{label} upload returned {res.status_code}")
            elif res.status_code in (200, 201, 400, 415):
                R.ok(f"{label} upload endpoint safely handled ({res.status_code})")
            elif res.status_code == 404:
                R.fail(f"{label} upload endpoint returned 404")
            else:
                R.warn(f"{label} upload returned {res.status_code}")
        res, _ = request_json(s, "POST", "/messages/api/send", {
            "thread_id": thread_id,
            "body": f"{TEST_PREFIX}{unique_test_id()} location PHASE134_TEST_Windhoek",
            "message_type": "location",
            "lat": -22.5609,
            "lng": 17.0658,
            "label": "PHASE134_TEST_Windhoek",
        })
        R.ok("location message endpoint works") if res.status_code in (200, 201) else R.fail(f"location message returned {res.status_code}") if res.status_code >= 500 else R.warn(f"location message returned {res.status_code}")
        R.warn("media cleanup endpoint not confirmed; cleanup script will dry-run local tmp files")

R.summary("PHASE 134 - AUTHENTICATED MEDIA FLOW")

