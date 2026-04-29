import logging
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from wallet.services import active_membership_for, ensure_wallet

from .models import AccountRole


VERIFICATION_SALT = "namvibe-email-verification"
logger = logging.getLogger(__name__)


def is_valid_uuid(value):
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def account_rank_for_value(value):
    try:
        score = int(float(value or 0))
    except (TypeError, ValueError):
        score = 0

    if score >= 2000:
        return {"label": "King", "tone": "king", "icon": "👑", "score": score}
    if score >= 1000:
        return {"label": "Legend", "tone": "legend", "icon": "★", "score": score}
    if score >= 500:
        return {"label": "Vibe Knight", "tone": "knight", "icon": "⬢", "score": score}
    if score >= 200:
        return {"label": "Vibe", "tone": "vibe", "icon": "✦", "score": score}
    return {"label": "Namvibe", "tone": "namvibe", "icon": "●", "score": score}


def master_admin_email():
    return (getattr(settings, "MASTER_ADMIN_EMAIL", "") or "").lower().strip()


def master_admin_supabase_uid():
    return (getattr(settings, "MASTER_ADMIN_SUPABASE_UID", "") or "").strip()


def master_admin_dashboard_url():
    return reverse("support_control")


def master_admin_diagnostic_snapshot():
    configured_email = master_admin_email()
    configured_uid = master_admin_supabase_uid()

    matching_email_users = list(
        AccountRole.objects.filter(user__email__iexact=configured_email)
        .select_related("user")
        .order_by("user__id")
    ) if configured_email else []
    matching_uid_roles = list(
        AccountRole.objects.filter(supabase_uid=configured_uid).select_related("user").order_by("user__id")
    ) if configured_uid else []

    canonical_role = None
    if matching_uid_roles:
        canonical_role = matching_uid_roles[0]
    elif matching_email_users:
        canonical_role = matching_email_users[0]

    bypass_roles = []
    if canonical_role:
        bypass_roles = [
            role for role in matching_uid_roles
            if role.user_id != canonical_role.user_id
        ]

    return {
        "configured_email": configured_email,
        "configured_supabase_uid": configured_uid,
        "canonical_user": getattr(canonical_role, "user", None),
        "canonical_role": canonical_role,
        "matching_email_roles": matching_email_users,
        "matching_uid_roles": matching_uid_roles,
        "bypass_roles": bypass_roles,
        "would_repair": bool(canonical_role)
        and (
            canonical_role.role != AccountRole.Role.MASTER_ADMIN
            or canonical_role.supabase_uid != configured_uid
            or any(bypass_roles)
        ),
    }


def is_master_admin(user, role=None):
    if not getattr(user, "is_authenticated", False):
        return False
    role = role or getattr(user, "account_role", None)
    user_email = (getattr(user, "email", "") or "").lower().strip()
    role_uid = (getattr(role, "supabase_uid", "") or "").strip()
    configured_email = master_admin_email()
    configured_uid = master_admin_supabase_uid()
    if configured_email or configured_uid:
        return bool(
            (configured_email and user_email == configured_email)
            or (configured_uid and role_uid == configured_uid)
        )
    return getattr(role, "role", "") == AccountRole.Role.MASTER_ADMIN


def repair_master_admin_user(user, *, supabase_uid="", email=""):
    role, _ = AccountRole.objects.get_or_create(user=user)
    configured_email = master_admin_email()
    configured_uid = master_admin_supabase_uid()
    normalized_email = (email or user.email or configured_email).lower().strip()
    normalized_uid = (supabase_uid or role.supabase_uid or configured_uid).strip()

    if configured_email and normalized_email and user.email != configured_email:
        user.email = configured_email
        user.save(update_fields=["email"])

    conflicting_qs = AccountRole.objects.filter(supabase_uid=configured_uid).exclude(user=user) if configured_uid else AccountRole.objects.none()
    conflicting_count = conflicting_qs.count() if configured_uid else 0
    if configured_uid:
        conflicting_qs.update(
            supabase_uid="",
            role=AccountRole.Role.MEMBER,
            can_manage_promos=False,
            can_manage_support=False,
            can_moderate_users=False,
        )
        if conflicting_count:
            logger.warning(
                "Normalized %s conflicting AccountRole rows away from master admin uid %s",
                conflicting_count,
                configured_uid,
            )

    role.supabase_uid = configured_uid or normalized_uid
    role.role = AccountRole.Role.MASTER_ADMIN
    role.can_manage_promos = True
    role.can_manage_support = True
    role.can_moderate_users = True
    role.save(
        update_fields=[
            "supabase_uid",
            "role",
            "can_manage_promos",
            "can_manage_support",
            "can_moderate_users",
            "updated_at",
        ]
    )

    profile = getattr(user, "profile", None)
    if profile:
        updates = []
        if not profile.is_verified:
            profile.is_verified = True
            updates.append("is_verified")
        if not profile.is_creator:
            profile.is_creator = True
            updates.append("is_creator")
        if updates:
            updates.append("updated_at")
            profile.save(update_fields=updates)

    account_profile = getattr(user, "account_profile", None)
    if account_profile:
        updates = []
        if configured_email and account_profile.email != configured_email:
            account_profile.email = configured_email
            updates.append("email")
        if not account_profile.email_verified:
            account_profile.email_verified = True
            updates.append("email_verified")
        if not account_profile.profile_completed:
            account_profile.profile_completed = True
            updates.append("profile_completed")
        if updates:
            updates.append("updated_at")
            account_profile.save(update_fields=updates)

    logger.info(
        "Master admin repair applied to user_id=%s username=%s email=%s supabase_uid=%s",
        user.id,
        user.username,
        user.email,
        role.supabase_uid,
    )
    return role


def email_backend_ready():
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if backend.endswith("console.EmailBackend") or backend.endswith("locmem.EmailBackend"):
        return True
    return bool(getattr(settings, "EMAIL_HOST", "") and getattr(settings, "EMAIL_HOST_USER", ""))


def build_email_verification_token(user):
    payload = {
        "user_id": user.id,
        "email": (user.email or "").lower(),
        "issued_at": int(timezone.now().timestamp()),
    }
    return signing.dumps(payload, salt=VERIFICATION_SALT)


def load_email_verification_token(token, max_age=60 * 60 * 24 * 3):
    return signing.loads(token, salt=VERIFICATION_SALT, max_age=max_age)


def verification_url(request, token):
    path = reverse("verify_email_confirm", kwargs={"token": token})
    return request.build_absolute_uri(path)


def send_verification_email(request, user):
    account_profile = getattr(user, "account_profile", None)
    if not account_profile:
        return False, "Your account profile is not ready yet."
    if account_profile.email_verified:
        return False, "Your email is already verified."
    if not email_backend_ready():
        return False, "Email sending is not configured yet. Add SMTP environment variables to enable verification emails."

    token = build_email_verification_token(user)
    verify_link = verification_url(request, token)
    context = {
        "user": user,
        "verify_link": verify_link,
        "support_email": getattr(settings, "SUPPORT_EMAIL", "support@namvibe.com"),
        "valid_days": 3,
    }
    subject = "Verify your Namvibe email"
    text_body = render_to_string("accounts/email_verification_email.txt", context)
    html_body = render_to_string("accounts/email_verification_email.html", context)
    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    account_profile.verification_sent_at = timezone.now()
    account_profile.save(update_fields=["verification_sent_at", "updated_at"])
    return True, "Verification email sent."


def ensure_account_role(user, *, supabase_uid=""):
    role, _ = AccountRole.objects.get_or_create(user=user)
    updates = []
    if supabase_uid and role.supabase_uid != supabase_uid:
        role.supabase_uid = supabase_uid
        updates.append("supabase_uid")

    master_email = master_admin_email()
    master_uid = master_admin_supabase_uid()
    user_email = (user.email or "").lower().strip()

    target_role = role.role
    if (master_email and user_email == master_email) or (master_uid and role.supabase_uid == master_uid):
        return repair_master_admin_user(user, supabase_uid=role.supabase_uid, email=user_email)
    elif role.role == AccountRole.Role.MASTER_ADMIN and not ((master_email and user_email == master_email) or (master_uid and role.supabase_uid == master_uid)):
        target_role = AccountRole.Role.MEMBER
        role.can_manage_promos = False
        role.can_manage_support = False
        role.can_moderate_users = False
        updates.extend(["can_manage_promos", "can_manage_support", "can_moderate_users"])

    if target_role != role.role:
        role.role = target_role
        updates.append("role")

    if updates:
        updates.append("updated_at")
        role.save(update_fields=list(dict.fromkeys(updates)))
    return role


def onboarding_items_for(user):
    account_profile = getattr(user, "account_profile", None)
    profile = getattr(user, "profile", None)
    wallet = getattr(user, "wallet", None) or ensure_wallet(user)
    membership = active_membership_for(user)

    items = [
        {
            "label": "Verify email",
            "done": bool(account_profile and account_profile.email_verified),
            "description": "Unlock trusted account features and delivery updates.",
            "url": reverse("verify_email_notice"),
        },
        {
            "label": "Add profile picture",
            "done": bool(profile and profile.avatar),
            "description": "Make your profile recognizable in stories, comments, and live.",
            "url": reverse("profile_edit"),
        },
        {
            "label": "Write bio",
            "done": bool(profile and profile.bio.strip()),
            "description": "Tell people what your Namvibe presence is about.",
            "url": reverse("profile_edit"),
        },
        {
            "label": "Create dating profile",
            "done": hasattr(user, "dating_profile"),
            "description": "Appear in dating discovery with safe public details only.",
            "url": reverse("dating_profile_edit"),
        },
        {
            "label": "Publish first post",
            "done": user.posts.exists(),
            "description": "Drop your first update, reel, flyer, or creator promo.",
            "url": reverse("studio"),
        },
        {
            "label": "Open wallet",
            "done": wallet.available_balance > 0 or wallet.pending_balance > 0 or membership is not None,
            "description": "Prepare for premium, gifts, and creator earnings.",
            "url": reverse("wallet_home"),
        },
    ]
    completed = sum(1 for item in items if item["done"])
    return items, int((completed / max(len(items), 1)) * 100)


def next_auth_redirect(request, user):
    role = getattr(user, "account_role", None)
    if is_master_admin(user, role=role):
        return master_admin_dashboard_url()
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return reverse("user_dashboard")


def verification_resend_url():
    return reverse("verify_email_resend")


def verification_login_hint():
    query = urlencode({"next": reverse("verify_email_notice")})
    return f"{reverse('login')}?{query}"
