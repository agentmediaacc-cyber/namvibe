from django.db.models import F
from django.shortcuts import get_object_or_404, redirect

from .models import Advertisement


def ad_click_view(request, id):
    ad = get_object_or_404(Advertisement, id=id)
    Advertisement.objects.filter(id=ad.id).update(click_count=F("click_count") + 1)
    return redirect(ad.destination_url or "/")
