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
        },
    )
