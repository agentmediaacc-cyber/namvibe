from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from .models import Advertisement


def ads_home_view(request):
    ads = Advertisement.objects.active_for(Advertisement.Placement.DISCOVER)[:12]
    return render(
        request,
        "ads/home.html",
        {
            "ads": ads,
            "placements": Advertisement.Placement.choices,
        },
    )


@login_required(login_url="login")
def ads_starter_view(request):
    return render(
        request,
        "ads/starter.html",
        {
            "active_ads": Advertisement.objects.filter(status=Advertisement.Status.ACTIVE).order_by("-priority", "-created_at")[:12],
        },
    )


def ad_click_view(request, id):
    ad = get_object_or_404(Advertisement, id=id)
    Advertisement.objects.filter(id=ad.id).update(click_count=F("click_count") + 1)
    return redirect(ad.destination_url or "/")
