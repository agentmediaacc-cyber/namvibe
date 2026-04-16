from urllib.parse import urlencode

from django.urls import reverse


def profile_navigation(request):
    dashboard_url = reverse("user_dashboard")
    login_url = reverse("login")

    if request.user.is_authenticated:
        smart_profile_url = dashboard_url
    else:
        smart_profile_url = f"{login_url}?{urlencode({'next': dashboard_url})}"

    return {
        "smart_profile_url": smart_profile_url,
        "profile_dashboard_url": dashboard_url,
    }
