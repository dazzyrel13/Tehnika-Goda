import os
import sys
import warnings
import ipaddress
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from celery.schedules import crontab

from core.admin_url import DEFAULT_ADMIN_URL_PREFIX

# --- Monkey patch removed (Clean integration required for Django upgrades) ---

# Initialize environment variables
env = environ.Env(DEBUG=(bool, False), USE_HTTPS=(bool, False))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Quick-start development settings - unsuitable for production
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
TESTING = "test" in sys.argv
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
# Docker healthchecks call http://127.0.0.1 — keep loopback hosts even in prod.
for _loopback in ("127.0.0.1", "localhost"):
    if _loopback not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_loopback)
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", default="")
ANALYTICS_ASYNC = env.bool("ANALYTICS_ASYNC", default=True)
ANALYTICS_RETENTION_DAYS = env.int("ANALYTICS_RETENTION_DAYS", default=90)
# When False (default), raw client IPs are not stored — visitor_id already mixes IP.
ANALYTICS_STORE_IP = env.bool("ANALYTICS_STORE_IP", default=False)
# Trust X-Real-IP / X-Forwarded-For from nginx (also implied by BEHIND_HTTPS_PROXY).
TRUST_PROXY_HEADERS = env.bool("TRUST_PROXY_HEADERS", default=False)
BEHIND_HTTPS_PROXY = env.bool("BEHIND_HTTPS_PROXY", default=False)
ADMIN_URL_PREFIX = env("ADMIN_URL_PREFIX", default=DEFAULT_ADMIN_URL_PREFIX)
# Non-empty = only these IPs/CIDRs may open the admin. Empty = disabled.
ADMIN_ALLOWED_IPS = env.list("ADMIN_ALLOWED_IPS", default=[])
# When True, staff must confirm login via email link (ADMIN_LOGIN_APPROVAL_EMAIL).
ADMIN_LOGIN_EMAIL_APPROVAL = env.bool("ADMIN_LOGIN_EMAIL_APPROVAL", default=False)
ADMIN_LOGIN_APPROVAL_EMAIL = (env("ADMIN_LOGIN_APPROVAL_EMAIL", default="") or "").strip()

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=465)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=True)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default=EMAIL_HOST_USER or "noreply@tehnikagoda.ru",
)

if (
    DEBUG
    and not TESTING
    and ("tehnikagoda.ru" in (SITE_URL or "").lower() or env.bool("USE_HTTPS", default=False))
):
    warnings.warn(
        "DEBUG=True with production-like SITE_URL/USE_HTTPS — keep local and prod .env files separate "
        "(.env.example vs .env.production.example).",
        RuntimeWarning,
        stacklevel=1,
    )

# Public review platforms (homepage widgets + fallback links for review cards)
REVIEW_YANDEX_URL = env("REVIEW_YANDEX_URL", default="")
REVIEW_2GIS_URL = env("REVIEW_2GIS_URL", default="")
REVIEW_AVITO_URL = env("REVIEW_AVITO_URL", default="")
# Rating/count are computed from published Review rows — not env placeholders.

# Search Console / Яндекс.Вебмастер (optional meta verification tokens)
GOOGLE_SITE_VERIFICATION = env("GOOGLE_SITE_VERIFICATION", default="")
YANDEX_VERIFICATION = env("YANDEX_VERIFICATION", default="")
# Public counter id only (digits). Empty = Metrika not loaded.
YANDEX_METRIKA_ID = (env("YANDEX_METRIKA_ID", default="") or "").strip()

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.sites",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "django_celery_results",
    "django_ckeditor_5",
    "django_cleanup.apps.CleanupConfig",
    "django_user_agents",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "formtools",
    "two_factor",
    "axes",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "analytics.apps.AnalyticsConfig",
    "catalog.apps.CatalogConfig",
    "leads.apps.LeadsConfig",
    "content.apps.ContentConfig",
    "utils.apps.UtilsConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security_middleware.SecurityHeadersMiddleware",
    "core.security_middleware.AdminIPAllowlistMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.security_middleware.SlidingAuthSessionMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.security_middleware.AdminEmailApprovalMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_user_agents.middleware.UserAgentMiddleware",
    "analytics.middleware.VisitAnalyticsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.seo",
            ],

        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# Database
DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")}
if (
    not TESTING
    and "postgresql" in (DATABASES["default"].get("ENGINE") or "")
):
    DATABASES["default"]["CONN_MAX_AGE"] = 60

# Cache (Redis — shared across workers and Celery)
# Uses REDIS_CACHE_URL (DB 1). Separate from Celery Broker (DB 0) to avoid key collisions.
if TESTING:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("REDIS_CACHE_URL", default="redis://localhost:6379/1"),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

_admin_index_path = "/" + (ADMIN_URL_PREFIX or DEFAULT_ADMIN_URL_PREFIX).lstrip("/")
if not _admin_index_path.endswith("/"):
    _admin_index_path += "/"
LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = _admin_index_path
LOGOUT_REDIRECT_URL = "two_factor:login"

# Staff sessions: 8h, sliding window via SlidingAuthSessionMiddleware.
# Anonymous hits do not rewrite Redis/DB on every request.
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # Django admin JS reads csrftoken

TWO_FACTOR_PATCH_ADMIN = True
TWO_FACTOR_LOGIN_TIMEOUT = 600

AXES_ENABLED = not TESTING
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_USERNAME_FORM_FIELD = "auth-username"
AXES_PASSWORD_FORM_FIELD = "auth-password"
AXES_CLIENT_IP_CALLABLE = "utils.client_ip.get_client_ip_for_axes"
AXES_LOCKOUT_TEMPLATE = "two_factor/lockout.html"
AXES_ENABLE_ADMIN = False  # do not expose lockout logs in the simplified admin

# Internationalization
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Upload limits (anti-abuse)
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB total POST
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB per file in-memory threshold

# Site Configuration
SITE_ID = 1

# Celery Configuration
# Celery Broker on DB 0, Cache on DB 1 — explicitly separated to avoid collisions
CELERY_BROKER_URL = env("REDIS_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_ALWAYS_EAGER = TESTING
CELERY_TASK_EAGER_PROPAGATES = TESTING

# CKEditor 5 Configuration
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "heading",
            "|",
            "bold",
            "italic",
            "link",
            "bulletedList",
            "numberedList",
            "blockQuote",
            "imageUpload",
        ],
    }
}

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    "cleanup-old-visit-events": {
        "task": "analytics.cleanup_old_visit_events_task",
        "schedule": crontab(minute=30, hour=3),  # Daily at 03:30 MSK
    },
}

# django-ratelimit: 429 instead of unhandled Ratelimited → 500
RATELIMIT_VIEW = "core.ratelimit.ratelimited_error"
# Use proxy-aware client IP (see utils.client_ip) instead of REMOTE_ADDR (= nginx).
RATELIMIT_IP_META_KEY = "utils.client_ip.get_client_ip_for_ratelimit"

# CSP helpers — Metrika hosts only when YANDEX_METRIKA_ID is set.
from core.csp import build_admin_csp, build_public_csp

CONTENT_SECURITY_POLICY = build_public_csp(yandex_metrika_id=YANDEX_METRIKA_ID)
CONTENT_SECURITY_POLICY_ADMIN = build_admin_csp()

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
)
CORS_ALLOW_CREDENTIALS = False

# Trust browser Origin/Referer for unsafe methods when using nginx or switching localhost vs 127.0.0.1
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
)

# Logging
Path(os.path.join(BASE_DIR, "logs")).mkdir(exist_ok=True)
Path(os.path.join(BASE_DIR, "staticfiles")).mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "catalog": {"level": "INFO"},
        "leads": {"level": "INFO"},
        "utils": {"level": "INFO"},
    },
}

# Production Security Settings
if env("USE_HTTPS") and not TESTING:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    if BEHIND_HTTPS_PROXY:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    X_FRAME_OPTIONS = "SAMEORIGIN"

if not DEBUG and not env("USE_HTTPS"):
    if env.bool("ALLOW_INSECURE_PRODUCTION", default=False):
        warnings.warn(
            "DEBUG=False with USE_HTTPS=False and ALLOW_INSECURE_PRODUCTION=True — "
            "cookies and transport are not hardened.",
            RuntimeWarning,
            stacklevel=2,
        )
    else:
        raise ImproperlyConfigured(
            "Production mode requires USE_HTTPS=True, or set ALLOW_INSECURE_PRODUCTION=True "
            "only for exceptional non-HTTPS deployments."
        )

if not DEBUG and not TESTING and not ADMIN_ALLOWED_IPS and not ADMIN_LOGIN_EMAIL_APPROVAL:
    if env.bool("ALLOW_OPEN_ADMIN", default=False):
        warnings.warn(
            "DEBUG=False with empty ADMIN_ALLOWED_IPS and ALLOW_OPEN_ADMIN=True — "
            "admin IP allowlist is disabled.",
            RuntimeWarning,
            stacklevel=2,
        )
    else:
        raise ImproperlyConfigured(
            "Production mode requires ADMIN_ALLOWED_IPS, ADMIN_LOGIN_EMAIL_APPROVAL=True, "
            "or set ALLOW_OPEN_ADMIN=True only as a temporary exception."
        )

if not DEBUG and not TESTING and ADMIN_LOGIN_EMAIL_APPROVAL:
    if not ADMIN_LOGIN_APPROVAL_EMAIL:
        raise ImproperlyConfigured(
            "ADMIN_LOGIN_EMAIL_APPROVAL=True requires ADMIN_LOGIN_APPROVAL_EMAIL."
        )
    if not EMAIL_HOST or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        raise ImproperlyConfigured(
            "ADMIN_LOGIN_EMAIL_APPROVAL=True requires EMAIL_HOST, EMAIL_HOST_USER, "
            "and EMAIL_HOST_PASSWORD (e.g. smtp.mail.ru)."
        )

_invalid_admin_ips = []
for _raw in ADMIN_ALLOWED_IPS:
    _raw = (_raw or "").strip()
    if not _raw:
        continue
    try:
        ipaddress.ip_network(_raw, strict=False)
    except ValueError:
        _invalid_admin_ips.append(_raw)
if _invalid_admin_ips and not DEBUG and not TESTING:
    raise ImproperlyConfigured(
        "Invalid ADMIN_ALLOWED_IPS entries (typos disable the allowlist): "
        + ", ".join(_invalid_admin_ips)
    )
