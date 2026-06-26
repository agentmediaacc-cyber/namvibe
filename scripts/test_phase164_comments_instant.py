#!/usr/bin/env python3
"""Phase 164: Verify instant comment posting, delete, and notification event types."""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASS = 0
FAIL = 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")

post_detail = open("templates/posts/detail.html").read()
reel_detail = open("templates/reels/detail.html").read()

print("=== Phase 164 — Comments Instant Posting ===")

# 1. Post detail: no page reload after comment
check("post/detail.html: no location.reload after comment",
      "location.reload" not in post_detail,
      "should not reload page after comment")

# 2. Post detail: addCommentToDOM function
check("post/detail.html: addCommentToDOM exists",
      "addCommentToDOM" in post_detail)

# 3. Post detail: temp comment created before API
check("post/detail.html: optimistic DOM insert before API call",
      "addCommentToDOM(body, tempId)" in post_detail)

# 4. Post detail: rollback removes temp comment
check("post/detail.html: rollback removes temp comment",
      "tempEl.remove()" in post_detail)

# 5. Post detail: delete comment route
check("post/detail.html: delete-comment handler exists",
      "data-action=delete-comment" in post_detail)

check("post/detail.html: delete uses /api/comments/<id>",
      "/api/comments/" in post_detail)

# 6. Post detail: escapeHtml function
check("post/detail.html: escapeHtml exists",
      "function escapeHtml" in post_detail)

# 7. Post detail: profile data on submit button
check("post/detail.html: data-username on submit",
      "data-username" in post_detail)

check("post/detail.html: data-avatar on submit",
      "data-avatar" in post_detail)

# 8. Reel detail: no location.reload after comment
check("reel/detail.html: no location.reload after comment",
      "location.reload" not in reel_detail,
      "should not reload page after comment")

# 9. Reel detail: addCommentToDOM function
check("reel/detail.html: addCommentToDOM exists",
      "addCommentToDOM" in reel_detail)

# 10. Reel detail: optimistic DOM insert
check("reel/detail.html: optimistic DOM insert before API",
      "addCommentToDOM(body, tempId)" in reel_detail)

# 11. Reel detail: rollback on error
check("reel/detail.html: rollback removes temp comment",
      "tempEl.remove()" in reel_detail)

# 12. Reel detail: escapeHtml function
check("reel/detail.html: escapeHtml exists",
      "function escapeHtml" in reel_detail)

# 13. Reel detail: data-comment-id on comment divs
check("reel/detail.html: data-comment-id on comments",
      "data-comment-id" in reel_detail)

# 14. Reel detail: profile data on submit
check("reel/detail.html: data-username on submit",
      "data-username" in reel_detail)

check("reel/detail.html: data-avatar on submit",
      "data-avatar" in reel_detail)

# 15. Engagement service: comment config has 'comment' event type
engagement = open("services/engagement_service.py").read()
check("engagement_service.py: comment event_type='comment' for posts",
      '"event_type": "comment"' in engagement)

# 16. Delete comment route available
comments_routes = open("api_routes/comments_routes.py").read()
check("comments_routes.py: DELETE /<comment_id> exists",
      'methods=["DELETE"]' in comments_routes)

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
