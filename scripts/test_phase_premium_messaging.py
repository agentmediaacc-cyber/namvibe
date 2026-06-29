#!/usr/bin/env python3
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def emit(status, name, detail=""):
    print(f"{status} [{name}] {detail}")
    return status == "PASS"


def check(name, condition, detail, failures):
    emit("PASS" if condition else "FAIL", name, detail)
    if not condition:
        failures.append(f"{name}: {detail}")


def main():
    failures = []

    try:
        message_routes = importlib.import_module("api_routes.message_routes")
        emit("PASS", "import_message_routes", "api_routes.message_routes imported")
    except Exception as error:
        emit("FAIL", "import_message_routes", str(error))
        return 1

    routes_text = (ROOT / "api_routes/message_routes.py").read_text(encoding="utf-8")
    check("route_send", '@message_bp.route("/api/messages/send"' in routes_text, "send route registered", failures)
    check("route_reaction", '/api/messages/<message_id>/reaction' in routes_text and '/api/message/<message_id>/react' in routes_text, "reaction route registered", failures)
    check("route_edit", '/api/messages/<message_id>/edit' in routes_text, "edit route registered", failures)
    check("route_delete", '/api/messages/<message_id>/delete' in routes_text, "delete route registered", failures)
    check("route_search", '@message_bp.route("/api/messages/search")' in routes_text, "search route registered", failures)
    check("route_wallpaper", '/api/threads/<thread_id>/wallpaper' in routes_text, "wallpaper route registered", failures)

    from services import message_feature_service as mfs

    check("service_reactions", hasattr(mfs, "add_reaction") and hasattr(mfs, "get_reactions"), "reaction helpers available", failures)
    check("service_reply_send", hasattr(mfs, "send_text_message"), "text send helper available", failures)
    check("service_edit_delete", hasattr(mfs, "edit_message") and hasattr(mfs, "delete_message"), "edit/delete helpers available", failures)
    check("service_search", hasattr(mfs, "search_messages"), "message search helper available", failures)

    thread_template = (ROOT / "templates/messages/thread.html").read_text(encoding="utf-8")
    pro_js = (ROOT / "static/js/namvibe_messages_pro.js").read_text(encoding="utf-8")
    check("ui_reaction_handlers", "toggleReaction" in thread_template and "reaction-badge" in thread_template, "thread reaction UI wired", failures)
    check("ui_reply_handlers", "initReplyFromMsg" in thread_template and "parent_message_id" in thread_template, "thread reply UI wired", failures)
    check("ui_upload_preview", "attachment-preview" in thread_template and "showAttachmentPreview" in pro_js, "attachment preview UI wired", failures)
    check("ui_voice_progress", "vp-progress" in thread_template and "XMLHttpRequest" in pro_js, "voice upload progress UI wired", failures)
    check("ui_mobile_gestures", "handleSwipe" in thread_template and "touchstart" in thread_template, "swipe-to-reply handlers present", failures)
    check("ui_search", "thread-search-input" in thread_template and "api/messages/search" in routes_text, "thread search UI and route present", failures)
    check("real_profile_links", "/profile/@" not in thread_template or "/profile/@{{" in thread_template or "url_for(" in thread_template, "no broken literal profile links in thread template", failures)
    check("friend_gate", "friendship_required" in routes_text and "require_friendship_or_403" in routes_text, "friend gate still enforced in send route", failures)
    check("no_fake_messages", "demo message" not in (thread_template + pro_js + routes_text).lower(), "no fake message content in premium messaging surfaces", failures)

    if failures:
        emit("FAIL", "summary", f"{len(failures)} checks failed")
        return 1
    emit("PASS", "summary", "premium messaging checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
