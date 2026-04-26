from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        verified = False
        try:
            verified = user.profile.email_verified
        except Exception:
            verified = False
        return f"{user.pk}{timestamp}{verified}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()
