"""
config/settings/production.py — Production-environment overrides.

Tightens security settings, requires explicit environment variables, and
configures the database from a DATABASE_URL connection string.
"""

import dj_database_url
from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

# ---------------------------------------------------------------------------
# WhiteNoise — serve static files without a dedicated web server
# ---------------------------------------------------------------------------

MIDDLEWARE.insert(  # noqa: F405 — MIDDLEWARE imported via wildcard from base
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

# GZipMiddleware compresses dynamic responses; WhiteNoise handles its own
# compression for static files.
# NOTE: GZip + HTTPS + reflected user input can be vulnerable to the BREACH
# attack. Keep that in mind before adding pages that echo user-supplied
# content back into an authenticated response.
MIDDLEWARE.insert(  # noqa: F405
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,  # noqa: F405
    "django.middleware.gzip.GZipMiddleware",
)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")

# ---------------------------------------------------------------------------
# Cache — shared across workers
# ---------------------------------------------------------------------------
# base.py's LocMemCache is per-process, which would give the sign-in throttle
# one bucket per worker and multiply the rate limit by the worker count.
# DatabaseCache needs no extra service; move to Redis when there is traffic to
# justify one. Requires `manage.py createcachetable`.

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    },
}

# ---------------------------------------------------------------------------
# Database — expects DATABASE_URL, e.g. postgresql://user:pw@host:5432/db
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Platforms that terminate TLS at the proxy forward the original scheme in
# this header; without it Django sees plain HTTP and SECURE_SSL_REDIRECT
# would loop.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
