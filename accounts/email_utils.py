from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def send_verification_email(request, user, token):
    link = request.build_absolute_uri(
        reverse("verify_email_confirm", args=[user.pk, token])
    )

    subject = "Verify your Namvibe account"
    message = (
        "Welcome to Namvibe.\\n\\n"
        "Click this link to verify your account:\\n\\n"
        f"{link}\\n\\n"
        "If you did not request this, ignore this email."
    )

    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "Namvibe <support@namvibe.com>"),
        [user.email],
        fail_silently=False,
    )
