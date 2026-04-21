# force rebuild
# Namvibe

## Email verification setup

Namvibe now supports verification-ready email delivery without hardcoded secrets.

Set these environment variables before enabling production email sending:

- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`
- `SUPPORT_EMAIL`

Example sender:

- `SUPPORT_EMAIL=support@namvibe.com`
- `DEFAULT_FROM_EMAIL=Namvibe <support@namvibe.com>`

If SMTP is not configured yet, signup and resend-verification flows degrade gracefully and show in-app guidance instead of failing hard.
