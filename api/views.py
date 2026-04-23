from django.http import JsonResponse

from accounts.models import Profile
from ads.models import Advertisement
from communities.models import Community
from live.models import LiveSession
from posts.models import Comment, Post, Report
from stories.models import StoryItem
from supportapp.models import SystemPromoCard
from wallet.models import MembershipPlan, UserMembership, WalletAccount, WalletTransaction


def _dashboard_payload(section, *, extra=None, safe_mode_message=""):
    payload = {"ok": True, "section": section}
    if safe_mode_message:
        payload["safe_mode"] = True
        payload["safe_mode_message"] = safe_mode_message
    if extra:
        payload.update(extra)
    return payload


def _stats_snapshot():
    return {
        "profiles": Profile.objects.count(),
        "posts": Post.objects.published().count(),
        "stories": StoryItem.objects.active().count(),
        "live_sessions": LiveSession.objects.exclude(status=LiveSession.Status.ENDED).count(),
        "ads": Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).count(),
        "promo_cards": SystemPromoCard.objects.filter(is_active=True).count(),
        "communities": Community.objects.count(),
        "memberships": UserMembership.objects.filter(status=UserMembership.Status.ACTIVE).count(),
    }


def api_root(request):
    safe_mode_message = ""
    try:
        payload = {"product": "Namvibe", "stats": _stats_snapshot()}
    except Exception as exc:
        payload = {"product": "Namvibe", "stats": {}}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("root", extra=payload, safe_mode_message=safe_mode_message))


def dashboard_home(request):
    safe_mode_message = ""
    try:
        payload = {
            "stats": _stats_snapshot(),
            "links": {
                "users": "/api/dashboard/users/",
                "posts": "/api/dashboard/posts/",
                "wallet": "/api/dashboard/wallet/",
                "support": "/api/dashboard/support/",
                "reports": "/api/dashboard/reports/",
            },
        }
    except Exception as exc:
        payload = {"stats": {}, "links": {}}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("dashboard", extra=payload, safe_mode_message=safe_mode_message))


def dashboard_users(request):
    safe_mode_message = ""
    try:
        payload = {
            "profiles": Profile.objects.count(),
            "wallet_accounts": WalletAccount.objects.count(),
            "active_memberships": UserMembership.objects.filter(status=UserMembership.Status.ACTIVE).count(),
        }
    except Exception as exc:
        payload = {"profiles": 0, "wallet_accounts": 0, "active_memberships": 0}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("dashboard_users", extra=payload, safe_mode_message=safe_mode_message))


def dashboard_posts(request):
    safe_mode_message = ""
    try:
        payload = {
            "published_posts": Post.objects.published().count(),
            "draft_posts": Post.objects.filter(status=Post.Status.DRAFT).count(),
            "comments": Comment.objects.count(),
            "active_stories": StoryItem.objects.active().count(),
        }
    except Exception as exc:
        payload = {"published_posts": 0, "draft_posts": 0, "comments": 0, "active_stories": 0}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("dashboard_posts", extra=payload, safe_mode_message=safe_mode_message))


def dashboard_wallet(request):
    safe_mode_message = ""
    try:
        payload = {
            "wallet_accounts": WalletAccount.objects.count(),
            "transactions": WalletTransaction.objects.count(),
            "active_memberships": UserMembership.objects.filter(status=UserMembership.Status.ACTIVE).count(),
            "plans": MembershipPlan.objects.filter(is_active=True).count(),
        }
    except Exception as exc:
        payload = {"wallet_accounts": 0, "transactions": 0, "active_memberships": 0, "plans": 0}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("dashboard_wallet", extra=payload, safe_mode_message=safe_mode_message))


def dashboard_support(request):
    safe_mode_message = ""
    try:
        payload = {
            "promo_cards": SystemPromoCard.objects.filter(is_active=True).count(),
            "active_ads": Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).count(),
            "live_rooms": LiveSession.objects.exclude(status=LiveSession.Status.ENDED).count(),
        }
    except Exception as exc:
        payload = {"promo_cards": 0, "active_ads": 0, "live_rooms": 0}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("dashboard_support", extra=payload, safe_mode_message=safe_mode_message))


def dashboard_reports(request):
    safe_mode_message = ""
    try:
        payload = {
            "post_reports": Report.objects.count(),
            "comment_flags": Comment.objects.filter(is_pinned=True).count(),
            "support_cards": SystemPromoCard.objects.filter(dismissible=False).count(),
        }
    except Exception as exc:
        payload = {"post_reports": 0, "comment_flags": 0, "support_cards": 0}
        safe_mode_message = str(exc)
    return JsonResponse(_dashboard_payload("dashboard_reports", extra=payload, safe_mode_message=safe_mode_message))
