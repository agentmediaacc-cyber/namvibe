from django.http import JsonResponse

def api_root(request):
    return JsonResponse({
        "ok": True,
        "message": "Eharo API is running"
    })

def dashboard_home(request):
    return JsonResponse({
        "ok": True,
        "section": "dashboard",
        "message": "Dashboard API home"
    })

def dashboard_users(request):
    return JsonResponse({
        "ok": True,
        "section": "dashboard_users",
        "message": "Users endpoint ready"
    })

def dashboard_posts(request):
    return JsonResponse({
        "ok": True,
        "section": "dashboard_posts",
        "message": "Posts endpoint ready"
    })

def dashboard_wallet(request):
    return JsonResponse({
        "ok": True,
        "section": "dashboard_wallet",
        "message": "Wallet endpoint ready"
    })

def dashboard_support(request):
    return JsonResponse({
        "ok": True,
        "section": "dashboard_support",
        "message": "Support endpoint ready"
    })

def dashboard_reports(request):
    return JsonResponse({
        "ok": True,
        "section": "dashboard_reports",
        "message": "Reports endpoint ready"
    })
