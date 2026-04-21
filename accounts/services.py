from urllib.parse import urlencode

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

    master_email = getattr(settings, "MASTER_ADMIN_EMAIL", "").lower().strip()
    master_uid = getattr(settings, "MASTER_ADMIN_SUPABASE_UID", "").strip()
    user_email = (user.email or "").lower().strip()

    target_role = role.role
    if master_email and user_email == master_email and master_uid and role.supabase_uid == master_uid:
        target_role = AccountRole.Role.MASTER_ADMIN
        role.can_manage_promos = True
        role.can_manage_support = True
        role.can_moderate_users = True
        updates.extend(["can_manage_promos", "can_manage_support", "can_moderate_users"])
    elif role.role == AccountRole.Role.MASTER_ADMIN and not (master_email and user_email == master_email and master_uid and role.supabase_uid == master_uid):
        target_role = AccountRole.Role.MEMBER

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
            "label": "Add avatar",
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
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    account_profile = getattr(user, "account_profile", None)
    if account_profile and (not account_profile.profile_completed or not account_profile.email_verified):
        return reverse("profile_completion")
    return reverse("user_dashboard")


def verification_resend_url():
    return reverse("verify_email_resend")


def verification_login_hint():
    query = urlencode({"next": reverse("verify_email_notice")})
    return f"{reverse('login')}?{query}"
