#!/usr/bin/env python3
"""Phase 7 Creator Studio — Functional Tests (20+ tests)."""

import json, os, sys, traceback, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
ERRORS = []

def test(label, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  ✅ {label}")
    except Exception as e:
        FAIL += 1
        msg = f"  ❌ {label} — {e}"
        ERRORS.append(msg)
        print(msg)
        traceback.print_exc()

from services.creator_studio_service import (
    get_studio_dashboard,
    get_studio_analytics,
    get_studio_earnings,
    get_earnings_by_type,
    get_transaction_history,
    check_duplicate_payout,
    get_drafts, create_draft, update_draft, delete_draft,
    get_scheduled_posts, create_scheduled_post, cancel_scheduled_post,
    archive_content, restore_content, get_archived_content,
    get_keyword_filters, add_keyword_filter, remove_keyword_filter,
    get_hidden_words, add_hidden_word, remove_hidden_word,
    get_review_queue, approve_review_item, reject_review_item,
    get_link_hub, add_link_hub, remove_link_hub,
    get_contact_info, set_contact_info,
    get_business_hours, set_business_hours, update_business_profile,
    get_milestones, check_and_notify_milestones, get_or_create_weekly_summary,
)

TEST_PROFILE_ID = str(uuid.uuid4())

print("=" * 60)
print("Phase 7 — Creator Studio Tests")
print("=" * 60)

# 1. Dashboard
def t1():
    r = get_studio_dashboard(TEST_PROFILE_ID)
    assert isinstance(r, dict), "must be dict"
    assert "ok" in r, "must have ok field"
    assert "overview" in r, "must have overview field"
test("1. get_studio_dashboard returns dict with ok + overview", t1)

# 2. Analytics
def t2():
    r = get_studio_analytics(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("2. get_studio_analytics returns dict", t2)

# 3. Analytics with period
def t3():
    r = get_studio_analytics(TEST_PROFILE_ID, period="monthly", days=60)
    assert isinstance(r, dict)
test("3. Analytics monthly period", t3)

# 4. Earnings
def t4():
    r = get_studio_earnings(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("4. get_studio_earnings returns dict", t4)

# 5. Earnings by type
def t5():
    r = get_earnings_by_type(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("5. get_earnings_by_type returns dict", t5)

# 6. Transaction history
def t6():
    r = get_transaction_history(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("6. get_transaction_history returns dict", t6)

# 7. Duplicate payout check
def t7():
    r = check_duplicate_payout(TEST_PROFILE_ID, 1000, "ref-test-" + str(uuid.uuid4()))
    assert isinstance(r, dict)
    assert "ok" in r
test("7. check_duplicate_payout returns dict", t7)

# 8. Drafts
def t8():
    r = get_drafts(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("8. get_drafts returns dict", t8)

# 9. Create draft
def t9():
    r = create_draft(TEST_PROFILE_ID, "post", "Test Draft", "Body", "https://example.com/img.jpg", {})
    assert isinstance(r, dict)
test("9. create_draft returns dict", t9)

# 10. Update draft
def t10():
    r = create_draft(TEST_PROFILE_ID, "post", "To Update", "Body", None, None)
    if r.get("ok"):
        did = r["draft"].get("id")
        if did:
            u = update_draft(did, title="Updated")
            assert u.get("ok") is True
test("10. update_draft", t10)

# 11. Delete draft
def t11():
    r = create_draft(TEST_PROFILE_ID, "post", "To Delete", "Body", None, None)
    if r.get("ok"):
        did = r["draft"].get("id")
        if did:
            d = delete_draft(did)
            assert d.get("ok") is True
test("11. delete_draft", t11)

# 12. Scheduled posts list
def t12():
    r = get_scheduled_posts(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("12. get_scheduled_posts returns dict", t12)

# 13. Create scheduled post
def t13():
    r = create_scheduled_post(TEST_PROFILE_ID, "2026-07-01T12:00:00Z", "post", "Scheduled", "Body", None, None)
    assert isinstance(r, dict)
test("13. create_scheduled_post returns dict", t13)

# 14. Cancel scheduled post
def t14():
    r = create_scheduled_post(TEST_PROFILE_ID, "2026-07-10T12:00:00Z", "post", "To Cancel", "Body", None, None)
    if r.get("ok"):
        sid = r["scheduled"].get("id")
        if sid:
            c = cancel_scheduled_post(sid)
            assert c.get("ok") is True
test("14. cancel_scheduled_post", t14)

# 15. Archive content
def t15():
    r = archive_content(TEST_PROFILE_ID, "post", str(uuid.uuid4()))
    assert isinstance(r, dict)
test("15. archive_content returns dict", t15)

# 16. Restore content
def t16():
    r = restore_content("post", str(uuid.uuid4()))
    assert isinstance(r, dict)
test("16. restore_content returns dict", t16)

# 17. Get archived content
def t17():
    r = get_archived_content(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("17. get_archived_content returns dict", t17)

# 18. Keyword filters
def t18():
    r = get_keyword_filters(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("18. get_keyword_filters returns dict", t18)

# 19. Add keyword filter
def t19():
    r = add_keyword_filter(TEST_PROFILE_ID, "badword", "hide")
    assert isinstance(r, dict)
    assert "ok" in r
test("19. add_keyword_filter returns dict", t19)

# 20. Remove keyword filter
def t20():
    r = add_keyword_filter(TEST_PROFILE_ID, "removeword", "hide")
    if r.get("ok"):
        fid = r["filter"].get("id")
        if fid:
            rm = remove_keyword_filter(fid)
            assert rm.get("ok") is True
test("20. remove_keyword_filter", t20)

# 21. Hidden words
def t21():
    r = get_hidden_words(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("21. get_hidden_words returns dict", t21)

# 22. Add hidden word
def t22():
    r = add_hidden_word(TEST_PROFILE_ID, "spamword")
    assert isinstance(r, dict)
    assert "ok" in r
test("22. add_hidden_word returns dict", t22)

# 23. Remove hidden word
def t23():
    r = remove_hidden_word(TEST_PROFILE_ID, "spamword")
    assert isinstance(r, dict)
test("23. remove_hidden_word returns dict", t23)

# 24. Review queue
def t24():
    r = get_review_queue(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("24. get_review_queue returns dict", t24)

# 25. Link hub
def t25():
    r = get_link_hub(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("25. get_link_hub returns dict", t25)

# 26. Add link hub
def t26():
    r = add_link_hub(TEST_PROFILE_ID, "My Site", "https://example.com", 1)
    assert isinstance(r, dict)
    assert "ok" in r
test("26. add_link_hub returns dict", t26)

# 27. Remove link hub
def t27():
    r = add_link_hub(TEST_PROFILE_ID, "Remove Me", "https://ex.com", 2)
    if r.get("ok"):
        lid = r["link"].get("id")
        if lid:
            rm = remove_link_hub(lid)
            assert rm.get("ok") is True
test("27. remove_link_hub", t27)

# 28. Contact info
def t28():
    r = get_contact_info(TEST_PROFILE_ID)
    assert isinstance(r, dict)
test("28. get_contact_info returns dict", t28)

# 29. Set contact info
def t29():
    r = set_contact_info(TEST_PROFILE_ID, "email", "creator@example.com", True)
    assert isinstance(r, dict)
test("29. set_contact_info returns dict", t29)

# 30. Business hours
def t30():
    r = get_business_hours(TEST_PROFILE_ID)
    assert isinstance(r, dict)
test("30. get_business_hours returns dict", t30)

# 31. Set business hours
def t31():
    r = set_business_hours(TEST_PROFILE_ID, 1, "09:00", "17:00", False)
    assert isinstance(r, dict)
test("31. set_business_hours returns dict", t31)

# 32. Update business profile
def t32():
    r = update_business_profile(TEST_PROFILE_ID, "creator", "Contact Me", "https://ex.com/contact")
    assert isinstance(r, dict)
test("32. update_business_profile returns dict", t32)

# 33. Milestones
def t33():
    r = get_milestones(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("33. get_milestones returns dict", t33)

# 34. Check milestones
def t34():
    r = check_and_notify_milestones(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("34. check_and_notify_milestones returns dict", t34)

# 35. Weekly summaries
def t35():
    r = get_or_create_weekly_summary(TEST_PROFILE_ID)
    assert isinstance(r, dict)
    assert "ok" in r
test("35. get_or_create_weekly_summary returns dict", t35)

# 36. Null handling
def t36():
    r = get_studio_dashboard(None)
    assert isinstance(r, dict)
test("36. Dashboard with None returns dict", t36)

print()
print("=" * 60)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed, {FAIL} failed")
if ERRORS:
    print("Errors:")
    for e in ERRORS:
        print(f"  {e}")
sys.exit(1 if FAIL else 0)
