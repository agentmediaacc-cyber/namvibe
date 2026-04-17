from django.contrib.auth import get_user_model
from django.db.models import Q

from accounts.models import Block, Mute
from .models import DatingLike, DatingPass, DatingProfile, DatingPreference, Match


def normalize_pair(user_a, user_b):
    return (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)


def blocked_user_ids_for(user):
    pairs = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
    return {item for pair in pairs for item in pair if item != user.id}


def matched_user_ids_for(user):
    pairs = Match.objects.filter(Q(user_one=user) | Q(user_two=user), is_active=True).values_list("user_one_id", "user_two_id")
    return {item for pair in pairs for item in pair if item != user.id}


def discovery_queryset_for(user, filters=None):
    filters = filters or {}
    excluded = {user.id}
    excluded |= blocked_user_ids_for(user)
    excluded |= matched_user_ids_for(user)
    excluded |= set(DatingPass.objects.filter(from_user=user).values_list("to_user_id", flat=True))

    qs = (
        DatingProfile.objects.filter(is_visible=True)
        .exclude(user_id__in=excluded)
        .select_related("user", "user__profile")
        .prefetch_related("photos")
    )

    gender = filters.get("gender", "").strip()
    city = filters.get("city", "").strip()
    region = filters.get("region", "").strip()
    goal = filters.get("relationship_goal", "").strip()
    verified = filters.get("verified") in {"1", "true", "on"}
    creator = filters.get("creator") in {"1", "true", "on"}
    age_min = filters.get("age_min")
    age_max = filters.get("age_max")

    if gender:
        qs = qs.filter(gender=gender)
    if city:
        qs = qs.filter(city__icontains=city)
    if region:
        qs = qs.filter(region__icontains=region)
    if goal:
        qs = qs.filter(relationship_goal=goal)
    if verified:
        qs = qs.filter(is_verified_dating=True)
    if creator:
        qs = qs.filter(user__profile__is_creator=True)

    # TODO(distance): replace city/region matching with geospatial distance when coordinates are stored.
    profiles = list(qs[:200])
    if age_min:
        profiles = [profile for profile in profiles if profile.age >= int(age_min)]
    if age_max:
        profiles = [profile for profile in profiles if profile.age <= int(age_max)]

    muted_ids = set(Mute.objects.filter(muter=user).values_list("muted_id", flat=True))
    profiles.sort(key=lambda profile: (profile.user_id in muted_ids, -profile.created_at.timestamp()))
    return profiles


def like_user(from_user, to_user):
    if from_user == to_user:
        return None, None
    if to_user.id in blocked_user_ids_for(from_user):
        return None, None
    DatingPass.objects.filter(from_user=from_user, to_user=to_user).delete()
    like, _ = DatingLike.objects.get_or_create(from_user=from_user, to_user=to_user)
    match = None
    if DatingLike.objects.filter(from_user=to_user, to_user=from_user).exists():
        user_one, user_two = normalize_pair(from_user, to_user)
        match, _ = Match.objects.get_or_create(user_one=user_one, user_two=user_two, defaults={"is_active": True})
        if not match.is_active:
            match.is_active = True
            match.save(update_fields=["is_active"])
    return like, match


def pass_user(from_user, to_user):
    if from_user == to_user:
        return None
    if to_user.id in blocked_user_ids_for(from_user):
        return None
    return DatingPass.objects.get_or_create(from_user=from_user, to_user=to_user)[0]


def matches_for(user):
    return (
        Match.objects.filter(Q(user_one=user) | Q(user_two=user), is_active=True)
        .select_related("user_one", "user_one__profile", "user_two", "user_two__profile", "user_one__dating_profile", "user_two__dating_profile")
        .order_by("-created_at")
    )
