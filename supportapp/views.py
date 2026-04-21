from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import render

from accounts.models import AccountRole
from ads.models import Advertisement
from live.models import LiveSession
from posts.models import Post
from stories.models import StoryItem
from wallet.models import MembershipPlan, UserMembership

from .models import SystemPromoCard


def support_home_view(request):
    return render(
        request,
        "supportapp/home.html",
        {
            "promo_cards": SystemPromoCard.objects.filter(is_active=True)[:6],
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
        },
    )


@login_required(login_url="login")
def support_control_view(request):
    role = getattr(request.user, "account_role", None)
    can_manage = bool(role and role.is_admin)
    if not can_manage:
        return HttpResponseForbidden("This control surface is restricted to approved support and admin accounts.")
    return render(
        request,
        "supportapp/control.html",
        {
            "role": role,
            "can_manage": can_manage,
            "support_metrics": {
                "users": User.objects.count(),
                "posts": Post.objects.published().count(),
                "stories": StoryItem.objects.active().count(),
                "live_sessions": LiveSession.objects.exclude(status=LiveSession.Status.ENDED).count(),
                "active_memberships": UserMembership.objects.filter(status=UserMembership.Status.ACTIVE).count(),
                "promo_cards": SystemPromoCard.objects.filter(is_active=True).count(),
                "ads": Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).count(),
                "plans": MembershipPlan.objects.filter(is_active=True).count(),
            },
            "promo_cards": SystemPromoCard.objects.all()[:12],
            "quick_links": [
                {"label": "Django admin", "url": "/admin/"},
                {"label": "Support route", "url": "/support/"},
                {"label": "Ads center", "url": "/ads/"},
                {"label": "API dashboard", "url": "/api/dashboard/"},
                {"label": "Wallet membership", "url": "/wallet/membership/plans/"},
                {"label": "Live rooms", "url": "/live/"},
            ],
            "team_roles": AccountRole.objects.exclude(role=AccountRole.Role.MEMBER).select_related("user")[:20],
            "control_sections": [
                {"title": "Moderation and reports", "copy": "Use Django admin today while moderation queues and report workflows deepen.", "url": "/admin/"},
                {"title": "Premium approvals", "copy": "Review memberships, plans, and upgrade friction from one route group.", "url": "/wallet/membership/plans/"},
                {"title": "Creator and streamer approvals", "copy": "Audit live hosts, creator roles, and monetization readiness.", "url": "/live/"},
                {"title": "Homepage featured content", "copy": "Seed promo cards and sponsored surfaces without changing templates again.", "url": "/support/"},
                {"title": "Broadcast and notifications", "copy": "Notifications and system promos can be reviewed from the social UX, not only admin.", "url": "/notifications/"},
                {"title": "Ads and promotions", "copy": "Open ads routes and promotion starter pages for creator/business growth.", "url": "/ads/promotions/"},
            ],
            "recent_ads": Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).order_by("-priority", "-created_at")[:6],
            "recent_live": LiveSession.objects.exclude(status=LiveSession.Status.ENDED).select_related("host", "host__profile").order_by("-viewer_count", "-created_at")[:6],
            "recent_posts": Post.objects.published().select_related("author", "author__profile").order_by("-published_at")[:6],
        },
    )
