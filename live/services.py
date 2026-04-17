from django.db.models import Q
from django.utils import timezone

from accounts.models import Block, Follow
from .models import LiveMessage, LiveSession
from wallet.services import user_has_live_access


def blocked_between(user, other_user):
    if not user.is_authenticated:
        return False
    return Block.objects.filter(Q(blocker=user, blocked=other_user) | Q(blocker=other_user, blocked=user)).exists()


def has_premium_live_access(user, session):
    return user_has_live_access(user, session)


def can_access_session(user, session):
    if user.is_authenticated and session.host_id == user.id:
        return True
    if blocked_between(user, session.host):
        return False
    if session.access_type == LiveSession.AccessType.PUBLIC:
        return True
    if not user.is_authenticated:
        return False
    if session.access_type == LiveSession.AccessType.FOLLOWERS:
        return Follow.objects.filter(follower=user, following=session.host).exists()
    if session.access_type == LiveSession.AccessType.PREMIUM:
        return has_premium_live_access(user, session)
    if session.access_type == LiveSession.AccessType.PRIVATE:
        return False
    return False


def can_chat(user, session):
    return user.is_authenticated and session.chat_enabled and session.status != LiveSession.Status.ENDED and can_access_session(user, session)


def visible_sessions_for(user):
    sessions = LiveSession.objects.select_related("host", "host__profile").prefetch_related("messages", "reactions")
    if user.is_authenticated:
        blocked_pairs = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
        hidden_ids = {item for pair in blocked_pairs for item in pair if item != user.id}
        sessions = sessions.exclude(host_id__in=hidden_ids)
    else:
        sessions = sessions.filter(access_type=LiveSession.AccessType.PUBLIC)
    return sessions


def live_now_for(user):
    return visible_sessions_for(user).filter(status=LiveSession.Status.LIVE).order_by("-is_featured", "-viewer_count", "-starts_at")


def featured_sessions_for(user):
    return visible_sessions_for(user).filter(is_featured=True).exclude(status=LiveSession.Status.ENDED).order_by("-viewer_count", "-starts_at")


def scheduled_sessions_for(user):
    return visible_sessions_for(user).filter(status=LiveSession.Status.SCHEDULED, starts_at__gte=timezone.now()).order_by("starts_at")


def related_sessions_for(user, session, limit=4):
    return live_now_for(user).exclude(pk=session.pk)[:limit]


def create_chat_message(user, session, body):
    if not can_chat(user, session):
        return None
    body = body.strip()
    if not body:
        return None
    return LiveMessage.objects.create(session=session, user=user, body=body)
