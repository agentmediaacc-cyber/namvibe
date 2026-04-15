from django.shortcuts import render, redirect

def live_studio_view(request):
    if not request.session.get("eharo_user_id"):
        return redirect("login")

    context = {
        "full_name": request.session.get("eharo_full_name", ""),
        "username": request.session.get("eharo_username", ""),
        "email": request.session.get("eharo_email", ""),
    }
    return render(request, "live/studio.html", context)
