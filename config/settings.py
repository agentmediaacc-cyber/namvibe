from pathlib import Path
import logging
import os
import sys
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def merged_env_list(name, default=None, extra=None):
    items = list(default or [])
    items.extend(env_list(name))
    items.extend(extra or [])
    merged = []
    for item in items:
        if item and item not in merged:
            merged.append(item)
    return merged


SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key")
DEBUG = env_bool("DEBUG", default=False)
if SECRET_KEY == "django-insecure-dev-key":
    logger.warning("SECRET_KEY is not set. Using the development fallback key.")
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'core',
    'accounts',
    'communities',
    'stories',
    'dating',
    'profiles',
    'posts',
    'reels',
    'messaging',
    'groupsapp',
    'wallet',
    'supportapp',
    'ads',
    'api',
    'livestream',
    'live',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.profile_navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

DATABASE_URL = os.getenv("DATABASE_URL", "")
RUNNING_TESTS = "test" in sys.argv
BUILD_WITHOUT_DB = env_bool("NAMVIBE_BUILD", default=False)
if not DATABASE_URL:
    if BUILD_WITHOUT_DB:
        logger.warning("DATABASE_URL is not set. Using build-only SQLite because NAMVIBE_BUILD=1.")
    elif DEBUG or RUNNING_TESTS:
        logger.warning("DATABASE_URL is not set. Falling back to local SQLite for local debug/test use only.")
    else:
        raise ImproperlyConfigured("DATABASE_URL must be configured for non-debug environments.")

default_database = dj_database_url.config(
    default=f"sqlite:///{'/tmp/namvibe-build.sqlite3' if BUILD_WITHOUT_DB else BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600,
    conn_health_checks=True,
    ssl_require=not DEBUG,
)
if default_database.get("ENGINE") == "django.db.backends.postgresql":
    default_database.setdefault("OPTIONS", {})
    default_database["OPTIONS"].setdefault("connect_timeout", 20)
    if not DEBUG:
        default_database["OPTIONS"]["sslmode"] = "require"

DATABASES = {"default": default_database}
logger.info(
    "Database configuration ready. DATABASE_URL exists=%s engine=%s",
    "yes" if bool(DATABASE_URL) else "no",
    DATABASES["default"].get("ENGINE", "unknown"),
)

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Windhoek'
USE_I18N = True
USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@namvibe.com")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"Namvibe <{SUPPORT_EMAIL}>")
MASTER_ADMIN_EMAIL = os.getenv("MASTER_ADMIN_EMAIL", "kasera@namvibe.com")
MASTER_ADMIN_SUPABASE_UID = os.getenv("MASTER_ADMIN_SUPABASE_UID", "2319f827-fc3c-46ce-9239-b350312a0d6f")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", SUPABASE_ANON_KEY)
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_KEY", ""))
SUPABASE_SERVICE_KEY = SUPABASE_SERVICE_ROLE_KEY
if not SUPABASE_URL or not SUPABASE_ANON_KEY or not SUPABASE_SERVICE_ROLE_KEY:
    logger.warning(
        "Supabase is not fully configured. Required env vars: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY."
    )

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

railway_hosts = [
    os.getenv("RAILWAY_PUBLIC_DOMAIN", ""),
    os.getenv("RAILWAY_PRIVATE_DOMAIN", ""),
    ".up.railway.app",
    ".railway.app",
    ".railway.internal",
]
default_allowed_hosts = ["localhost", "127.0.0.1", "testserver", "0.0.0.0", "www.namvibe.com", "namvibe.com"]
ALLOWED_HOSTS = merged_env_list("ALLOWED_HOSTS", default_allowed_hosts, railway_hosts)
if DEBUG and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("*")

default_csrf_origins = [
    "https://*.up.railway.app",
    "https://*.railway.app",
    "https://www.namvibe.com",
    "https://namvibe.com",
]
railway_csrf_origins = []
if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    railway_csrf_origins.append(f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}")
CSRF_TRUSTED_ORIGINS = merged_env_list("CSRF_TRUSTED_ORIGINS", default_csrf_origins, railway_csrf_origins)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
