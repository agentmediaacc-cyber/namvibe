from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from accounts.models import AccountRole
from accounts.services import ensure_account_role, is_master_admin, master_admin_dashboard_url, repair_master_admin_user
from ads.models import Advertisement
from live.models import LiveSession
from posts.models import Post
from stories.models import StoryItem
from wallet.models import MembershipPlan, UserMembership

from .models import SystemPromoCard


def support_home_view(request):
    if request.user.is_authenticated:
        role = ensure_account_role(request.user)
        if is_master_admin(request.user, role=role):
            return redirect(master_admin_dashboard_url())
    safe_mode_message = ""
    try:
        promo_cards = list(SystemPromoCard.objects.filter(is_active=True)[:6])
    except Exception as exc:
        promo_cards = []
        safe_mode_message = str(exc)
    return render(
        request,
        "supportapp/home.html",
        {
            "promo_cards": promo_cards,
            "support_routes": [
                {"label": "Notifications", "copy": "Open follows, chats, comments, and wallet alerts.", "url_name": "notifications"},
                {"label": "Wallet", "copy": "Review premium, gifts, and creator earnings.", "url_name": "wallet_home"},
                {"label": "Premium plans", "copy": "Upgrade or review membership routes.", "url_name": "wallet_membership_plans"},
                {"label": "Live home", "copy": "Open live discovery and viewer flows.", "url_name": "live_home"},
                {"label": "Creator Studio", "copy": "Launch content and monetization tools.", "url_name": "studio"},
                {"label": "Ads center", "copy": "Promotions, business tools, and feed ad routes.", "url_name": "ads_home"},
            ],
            "open_routes": [
                {"label": "Notifications", "url_name": "notifications"},
                {"label": "Wallet", "url_name": "wallet_home"},
                {"label": "Premium plans", "url_name": "wallet_membership_plans"},
                {"label": "Live home", "url_name": "live_home"},
                {"label": "Creator Studio", "url_name": "studio"},
            ],
            "safe_mode_message": safe_mode_message,
        },
    )


@login_required(login_url="login")
def support_control_view(request):
    role = ensure_account_role(request.user)
    if is_master_admin(request.user, role=role):
        role = repair_master_admin_user(
            request.user,
            supabase_uid=getattr(role, "supabase_uid", ""),
            email=request.user.email,
        )
    can_manage = bool(role and role.is_admin)
    if not can_manage:
        return HttpResponseForbidden("This control surface is restricted to approved support and admin accounts.")
    safe_mode_message = ""
    try:
        support_metrics = {
            "users": User.objects.count(),
            "posts": Post.objects.published().count(),
            "stories": StoryItem.objects.active().count(),
            "live_sessions": LiveSession.objects.exclude(status=LiveSession.Status.ENDED).count(),
            "active_memberships": UserMembership.objects.filter(status=UserMembership.Status.ACTIVE).count(),
            "promo_cards": SystemPromoCard.objects.filter(is_active=True).count(),
            "ads": Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).count(),
            "plans": MembershipPlan.objects.filter(is_active=True).count(),
        }
        promo_cards = list(SystemPromoCard.objects.all()[:12])
        team_roles = list(AccountRole.objects.exclude(role=AccountRole.Role.MEMBER).select_related("user")[:20])
        recent_ads = list(Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).order_by("-priority", "-created_at")[:6])
        recent_live = list(
            LiveSession.objects.exclude(status=LiveSession.Status.ENDED)
            .select_related("host", "host__profile")
            .order_by("-viewer_count", "-created_at")[:6]
        )
        recent_posts = list(
            Post.objects.published().select_related("author", "author__profile").order_by("-published_at")[:6]
        )
    except Exception as exc:
        safe_mode_message = str(exc)
        support_metrics = {
            "users": 0,
            "posts": 0,
            "stories": 0,
            "live_sessions": 0,
            "active_memberships": 0,
            "promo_cards": 0,
            "ads": 0,
            "plans": 0,
        }
        promo_cards = []
        team_roles = []
        recent_ads = []
        recent_live = []
        recent_posts = []
    return render(
        request,
        "supportapp/control.html",
        {
            "role": role,
            "can_manage": can_manage,
            "support_metrics": support_metrics,
            "promo_cards": promo_cards,
            "quick_links": [
                {"label": "Django admin", "url": "/admin/"},
                {"label": "Support route", "url": "/support/"},
                {"label": "Ads center", "url": "/ads/"},
                {"label": "API dashboard", "url": "/api/dashboard/"},
                {"label": "Wallet membership", "url": "/wallet/membership/plans/"},
                {"label": "Live rooms", "url": "/live/"},
            ],
            "team_roles": team_roles,
            "control_sections": [
                {"title": "Moderation and reports", "copy": "Use Django admin today while moderation queues and report workflows deepen.", "url": "/admin/"},
                {"title": "Premium approvals", "copy": "Review memberships, plans, and upgrade friction from one route group.", "url": "/wallet/membership/plans/"},
                {"title": "Creator and streamer approvals", "copy": "Audit live hosts, creator roles, and monetization readiness.", "url": "/live/"},
                {"title": "Homepage featured content", "copy": "Seed promo cards and sponsored surfaces without changing templates again.", "url": "/support/"},
                {"title": "Broadcast and notifications", "copy": "Notifications and system promos can be reviewed from the social UX, not only admin.", "url": "/notifications/"},
                {"title": "Ads and promotions", "copy": "Open ads routes and promotion starter pages for creator/business growth.", "url": "/ads/promotions/"},
            ],
            "recent_ads": recent_ads,
            "recent_live": recent_live,
            "recent_posts": recent_posts,
            "safe_mode_message": safe_mode_message,
        },
    )
