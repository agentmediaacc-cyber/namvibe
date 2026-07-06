#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = os.environ.get("NAMVIBE_PUBLIC_BASE_URL", "https://namvibe.com").rstrip("/")
LOGIN_URL = f"{BASE_URL}/auth/login"
HOME_URL = f"{BASE_URL}/"
CREDS_PATH = ROOT / "secrets" / "test_credentials.json"

SCREENSHOT_BEFORE = "/tmp/namvibe_home_before.png"
SCREENSHOT_AFTER_LIKE = "/tmp/namvibe_home_after_like.png"
SCREENSHOT_COMMENT_DRAWER = "/tmp/namvibe_comment_drawer.png"
SCREENSHOT_AFTER_COMMENT = "/tmp/namvibe_after_comment.png"


def load_credentials():
    data = json.loads(CREDS_PATH.read_text())
    candidates = [
        {"login_id": "alpha_user", "password": "TestPassword123!"},
        {"login_id": "alpha@namvibe.com", "password": "TestPassword123!"},
    ]
    user_a = data.get("user_a")
    if isinstance(user_a, dict):
        if user_a.get("email") and user_a.get("password"):
            candidates.append({"login_id": user_a.get("email"), "password": user_a.get("password")})
        if user_a.get("username") and user_a.get("password"):
            candidates.append({"login_id": user_a.get("username"), "password": user_a.get("password")})
    seen = set()
    deduped = []
    for candidate in candidates:
        key = (candidate.get("login_id"), candidate.get("password"))
        if key in seen or not key[0] or not key[1]:
            continue
        seen.add(key)
        deduped.append(candidate)
    if not deduped:
        raise SystemExit("No plaintext live test credentials found in secrets/test_credentials.json")
    return deduped


def click_if_visible(page, selectors):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=2000)
            if locator.is_visible():
                locator.click()
                return True
        except Exception:
            continue
    return False


def first_visible(page, selector):
    locator = page.locator(selector)
    count = locator.count()
    for index in range(count):
        candidate = locator.nth(index)
        try:
            candidate.wait_for(state="visible", timeout=1000)
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def extract_action_state(button):
    label = ""
    count_text = ""
    liked = ""
    try:
        label = button.locator(".nv-action-label").first.text_content(timeout=1000) or ""
    except Exception:
        pass
    try:
        count_text = button.locator(".nv-action-count").first.text_content(timeout=1000) or ""
    except Exception:
        pass
    try:
        liked = button.get_attribute("data-liked") or ""
    except Exception:
        pass
    return {
        "label": label.strip(),
        "count": count_text.strip(),
        "liked": liked,
    }


def like_button_selector(post_id):
    return f"[data-action='like'][data-post-id='{post_id}'], [data-action='like'][data-target-id='{post_id}']"


def comment_button_selector(post_id):
    return f"[data-action='comment'][data-post-id='{post_id}'], [data-action='comment'][data-target-id='{post_id}']"


def stable_post_card_selector():
    return "[data-type='post'][data-post-id]:not([data-live-room-id])"


def click_and_capture_json(page, locator, url_fragment, timeout=10000):
    locator.scroll_into_view_if_needed()
    with page.expect_response(lambda response: url_fragment in response.url and response.request.method == "POST", timeout=timeout) as response_info:
        locator.click(force=True)
    response = response_info.value
    payload = None
    try:
        payload = response.json()
    except Exception:
        payload = None
    return {"url": response.url, "status": response.status, "json": payload}


def login(page, credential_candidates):
    for creds in credential_candidates:
        print(f"LOGIN_ATTEMPT={creds['login_id']}", flush=True)
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.locator("input[name='login_id']").fill(creds["login_id"])
        page.locator("input[name='password']").fill(creds["password"])
        page.locator("button[type='submit'], .auth-submit-btn").first.click()
        page.wait_for_load_state("domcontentloaded", timeout=8000)
        page.wait_for_timeout(1000)
        login_error = ""
        if page.locator(".chain-auth-alert--error").count():
            login_error = (page.locator(".chain-auth-alert--error").first.text_content() or "").strip()
        if "/auth/login" not in page.url and not login_error:
            return creds, None
    return None, login_error or "Login stayed on /auth/login"


def print_json(label, payload):
    print(f"{label}: {json.dumps(payload, ensure_ascii=True, default=str)}", flush=True)


def main():
    credential_candidates = load_credentials()
    console_errors = []
    console_info = []
    failed_requests = []
    comment_statuses = []
    like_statuses = []

    with sync_playwright() as playwright:
        browser = None
        launch_errors = []
        for launch_kwargs in (
            {"headless": True, "channel": "chrome"},
            {"headless": True, "executable_path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"},
            {"headless": True},
        ):
            try:
                browser = playwright.chromium.launch(**launch_kwargs)
                break
            except Exception as error:
                launch_errors.append(str(error))
        if browser is None:
            raise SystemExit("Could not launch a browser: " + " | ".join(launch_errors))
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.add_init_script("window.__NAMVIBE_E2E_DISABLE_REFRESH__ = true;")

        page.on("console", lambda msg: (
            console_errors.append(msg.text) if msg.type == "error" else console_info.append(msg.text)
        ))
        page.on("requestfailed", lambda request: failed_requests.append({
            "url": request.url,
            "method": request.method,
            "failure": request.failure,
        }))

        def on_response(response):
            url = response.url
            if "/api/comments/post/" in url:
                payload = None
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                comment_statuses.append({"url": url, "status": response.status, "json": payload})
            if "/api/home/post/" in url and "/like" in url:
                payload = None
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                like_statuses.append({"url": url, "status": response.status, "json": payload})

        page.on("response", on_response)

        used_creds, login_error = login(page, credential_candidates)
        page.wait_for_timeout(1500)
        print(f"LOGIN_CREDENTIAL={used_creds}", flush=True)
        print(f"LOGIN_ERROR={login_error}", flush=True)
        if used_creds is None:
            raise SystemExit(f"Could not authenticate live browser user: {login_error}")
        try:
            page.goto(f"{HOME_URL}?e2e_no_refresh=1", wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(1500)

        build = page.evaluate("window.NAMVIBE_HOME_BUILD || null")
        ready = page.evaluate("window.NAMVIBE_HOME_INTERACTIONS_READY === true")
        try:
            page.wait_for_function("window.NAMVIBE_HOME_LIKES_READY === true", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        likes_ready = page.evaluate("window.NAMVIBE_HOME_LIKES_READY === true")
        print(f"NAMVIBE_HOME_BUILD={build}", flush=True)
        print(f"NAMVIBE_HOME_INTERACTIONS_READY={ready}", flush=True)
        print(f"NAMVIBE_HOME_LIKES_READY={likes_ready}", flush=True)

        page.screenshot(path=SCREENSHOT_BEFORE, full_page=True)

        post_card = first_visible(page, stable_post_card_selector())
        if not post_card:
            raise SystemExit("No stable real post card found on live homepage")
        post_id = post_card.get_attribute("data-post-id")
        if not post_id:
            raise SystemExit("Stable real post card did not expose data-post-id")
        print(f"REAL_POST_ID={post_id}", flush=True)
        like_button = post_card.locator("[data-action='like'][data-post-id]").first

        like_before = extract_action_state(like_button)
        print_json("LIKE_BEFORE", like_before)
        if like_before.get("liked") == "true":
            reset_response = click_and_capture_json(page, like_button, f"/api/home/post/{post_id}/like")
            page.wait_for_timeout(1000)
            like_button = page.locator(like_button_selector(post_id)).first
            like_reset = extract_action_state(like_button)
            print_json("LIKE_RESET_BEFORE_PROOF", like_reset)
            print_json("LIKE_RESET_RESPONSE", reset_response)
        like_response_first = click_and_capture_json(page, like_button, f"/api/home/post/{post_id}/like")
        page.wait_for_timeout(1000)
        like_button = page.locator(like_button_selector(post_id)).first
        like_after_first = extract_action_state(like_button)
        print_json("LIKE_AFTER_FIRST", like_after_first)
        print_json("LIKE_RESPONSE_FIRST", like_response_first)
        page.screenshot(path=SCREENSHOT_AFTER_LIKE, full_page=True)

        like_response_second = click_and_capture_json(page, like_button, f"/api/home/post/{post_id}/like")
        page.wait_for_timeout(1000)
        like_button = page.locator(like_button_selector(post_id)).first
        like_after_second = extract_action_state(like_button)
        print_json("LIKE_AFTER_SECOND", like_after_second)
        print_json("LIKE_RESPONSE_SECOND", like_response_second)

        comment_button = None
        comment_matches = page.locator(comment_button_selector(post_id))
        if comment_matches.count():
            comment_button = comment_matches.first
        else:
            comment_button = first_visible(page, "[data-action='comment'][data-post-id], [data-action='comment'][data-target-id]")
        if comment_button is None:
            raise SystemExit("No visible comment button found on live homepage")

        comment_before = extract_action_state(comment_button)
        print_json("COMMENT_BEFORE", comment_before)
        comment_button.click()
        page.wait_for_timeout(1200)
        page.screenshot(path=SCREENSHOT_COMMENT_DRAWER, full_page=True)

        input_locator = page.locator("#nv-comment-input, .nv-comment-composer textarea, .nv-comment-composer input[type='text']").first
        input_locator.wait_for(state="visible", timeout=5000)
        comment_text = f"Browser test comment {datetime.now(timezone.utc).isoformat()}"
        input_locator.fill(comment_text)

        submit_locator = page.locator("#nv-comment-submit, .nv-comment-submit, .nv-comment-form button[type='submit']").first
        submit_response = click_and_capture_json(page, submit_locator, f"/api/comments/post/{post_id}")
        page.wait_for_timeout(2000)
        page.screenshot(path=SCREENSHOT_AFTER_COMMENT, full_page=True)

        comment_button = page.locator(comment_button_selector(post_id)).first
        comment_after = extract_action_state(comment_button)
        print_json("COMMENT_AFTER", comment_after)
        print_json("COMMENT_RESPONSE", submit_response)

        auth_link_visible = page.locator("a[href='/auth/login'], a[href='/login']").first.is_visible() if page.locator("a[href='/auth/login'], a[href='/login']").count() else False
        comment_text_present = page.locator(f"text={comment_text}").count() > 0

        print_json("LIKE_STATUSES", like_statuses)
        print_json("COMMENT_STATUSES", comment_statuses)
        print_json("FAILED_REQUESTS", failed_requests)
        print_json("CONSOLE_ERRORS", console_errors)
        print_json("CONSOLE_INFO_TAIL", console_info[-20:])
        print(f"AUTH_LOGIN_LINK_VISIBLE={auth_link_visible}", flush=True)
        print(f"COMMENT_PRESENT={comment_text_present}", flush=True)
        print(f"SCREENSHOT_BEFORE={SCREENSHOT_BEFORE}", flush=True)
        print(f"SCREENSHOT_AFTER_LIKE={SCREENSHOT_AFTER_LIKE}", flush=True)
        print(f"SCREENSHOT_COMMENT_DRAWER={SCREENSHOT_COMMENT_DRAWER}", flush=True)
        print(f"SCREENSHOT_AFTER_COMMENT={SCREENSHOT_AFTER_COMMENT}", flush=True)

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except PlaywrightTimeoutError as error:
        raise SystemExit(f"Playwright timeout: {error}")
