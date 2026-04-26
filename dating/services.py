import logging
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Block, Mute
from .models import DatingCoinBalance, DatingLike, DatingPass, DatingProfile, Match


BOOST_COST_COINS = 50
SUPER_LIKE_COST_COINS = 20
logger = logging.getLogger(__name__)


def normalize_pair(user_a, user_b):
    return (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)


def _today_window():
    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(today, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


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

    # Sort by: boosted_at (desc, nulls last), is_verified_dating (desc), created_at (desc)
    muted_ids = set(Mute.objects.filter(muter=user).values_list("muted_id", flat=True))
    profiles.sort(key=lambda profile: (
        profile.user_id in muted_ids,
        -profile.boosted_at.timestamp() if profile.boosted_at else 0,
        profile.premium_tier == DatingProfile.PremiumTier.FREE,
        -1 if profile.is_verified_dating else 0,
        -profile.created_at.timestamp()
    ))
    return profiles


def coin_balance_for(user):
    return DatingCoinBalance.for_user(user)


def likes_used_today(user):
    start, end = _today_window()
    return DatingLike.objects.filter(
        from_user=user,
        created_at__gte=start,
        created_at__lt=end,
        is_super_like=False,
    ).count()


def remaining_likes_today(user):
    profile = getattr(user, "dating_profile", None)
    if not profile:
        return 0
    limit = profile.daily_like_limit
    if limit is None:
        return None
    return max(0, limit - likes_used_today(user))


def can_send_standard_like(user):
    remaining = remaining_likes_today(user)
    return remaining is None or remaining > 0


def _is_blocked_between(user_a, user_b):
    return Block.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


def _match_if_reciprocated(from_user, to_user):
    match = None
    if DatingLike.objects.filter(from_user=to_user, to_user=from_user).exists():
        user_one, user_two = normalize_pair(from_user, to_user)
        match, _ = Match.objects.get_or_create(user_one=user_one, user_two=user_two, defaults={"is_active": True})
        if not match.is_active:
            match.is_active = True
            match.save(update_fields=["is_active"])
    return match


def like_user(from_user, to_user, *, is_super_like=False):
    if from_user == to_user:
        return None, None
    if _is_blocked_between(from_user, to_user):
        return None, None
    with transaction.atomic():
        actor_profile = DatingProfile.objects.select_for_update().filter(user=from_user).first()
        if not actor_profile:
            return None, None

        existing_like = DatingLike.objects.select_for_update().filter(from_user=from_user, to_user=to_user).first()
        if existing_like:
            if is_super_like and not existing_like.is_super_like:
                existing_like.is_super_like = True
                existing_like.save(update_fields=["is_super_like"])
            match = _match_if_reciprocated(from_user, to_user)
            return existing_like, match

        if not is_super_like:
            limit = actor_profile.daily_like_limit
            if limit is not None and likes_used_today(from_user) >= limit:
                return None, None

        DatingPass.objects.filter(from_user=from_user, to_user=to_user).delete()
        like = DatingLike.objects.create(from_user=from_user, to_user=to_user, is_super_like=is_super_like)
        match = _match_if_reciprocated(from_user, to_user)
        return like, match


def boost_cooldown_hours_left(profile, *, now=None):
    now = now or timezone.now()
    if not profile.boosted_at:
        return 0
    cooldown_ends_at = profile.boosted_at + timedelta(hours=24)
    if cooldown_ends_at <= now:
        return 0
    return max(1, int((cooldown_ends_at - now).total_seconds() // 3600))


def purchase_boost(user):
    now = timezone.now()
    with transaction.atomic():
        profile = DatingProfile.objects.select_for_update().filter(user=user).first()
        if not profile:
            return {"ok": False, "reason": "missing_profile"}

        hours_left = boost_cooldown_hours_left(profile, now=now)
        if hours_left:
            return {"ok": False, "reason": "cooldown", "hours_left": hours_left}

        balance = DatingCoinBalance.objects.select_for_update().get(pk=DatingCoinBalance.for_user(user).pk)
        if balance.balance < BOOST_COST_COINS:
            return {"ok": False, "reason": "insufficient_coins"}

        balance.balance -= BOOST_COST_COINS
        balance.save(update_fields=["balance", "updated_at"])
        profile.boosted_at = now
        profile.save(update_fields=["boosted_at"])

    logger.info(
        "dating_coin_deduction user_id=%s amount=%s reason=boost balance_after=%s",
        user.id,
        BOOST_COST_COINS,
        balance.balance,
    )
    logger.info("dating_boost_used user_id=%s boosted_at=%s", user.id, now.isoformat())
    return {"ok": True, "balance_after": balance.balance, "boosted_at": now}


def purchase_super_like(from_user, to_user):
    if from_user == to_user:
        return {"ok": False, "reason": "forbidden"}
    if _is_blocked_between(from_user, to_user):
        return {"ok": False, "reason": "forbidden"}

    with transaction.atomic():
        actor_profile = DatingProfile.objects.select_for_update().filter(user=from_user).first()
        if not actor_profile:
            return {"ok": False, "reason": "missing_profile"}

        like = DatingLike.objects.select_for_update().filter(from_user=from_user, to_user=to_user).first()
        if like and like.is_super_like:
            return {"ok": False, "reason": "duplicate", "like": like}

        balance = DatingCoinBalance.objects.select_for_update().get(pk=DatingCoinBalance.for_user(from_user).pk)
        if balance.balance < SUPER_LIKE_COST_COINS:
            return {"ok": False, "reason": "insufficient_coins"}

        DatingPass.objects.filter(from_user=from_user, to_user=to_user).delete()

        if like:
            like.is_super_like = True
            like.save(update_fields=["is_super_like"])
        else:
            like = DatingLike.objects.create(from_user=from_user, to_user=to_user, is_super_like=True)

        match = _match_if_reciprocated(from_user, to_user)
        if not like.is_super_like:
            return {"ok": False, "reason": "forbidden"}

        balance.balance -= SUPER_LIKE_COST_COINS
        balance.save(update_fields=["balance", "updated_at"])

    logger.info(
        "dating_coin_deduction user_id=%s amount=%s reason=super_like target_user_id=%s balance_after=%s",
        from_user.id,
        SUPER_LIKE_COST_COINS,
        to_user.id,
        balance.balance,
    )
    logger.info(
        "dating_super_like_used user_id=%s target_user_id=%s match=%s",
        from_user.id,
        to_user.id,
        bool(match),
    )
    return {"ok": True, "like": like, "match": match, "balance_after": balance.balance}


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
