"""
config/settings/base.py — Shared Django settings for all environments.

Everything here is environment-agnostic: installed apps, middleware, template
configuration, logging, static files, i18n. Sensitive or environment-specific
values live in development.py / production.py and are read from the
environment via python-decouple.
"""

from pathlib import Path

from decouple import config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = config("SECRET_KEY")

# ---------------------------------------------------------------------------
# Release identifier
# ---------------------------------------------------------------------------
# Stamped into the static-asset query strings and available to templates, so a
# deploy invalidates stale browser entries. Hosting platforms usually expose
# the build commit SHA; locally it falls back to "dev".

RELEASE_VERSION = config(
    "RELEASE_VERSION",
    default=config("RENDER_GIT_COMMIT", default="dev"),
)

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_htmx",
    # Local
    "apps.core",
    "apps.accounts",
    "apps.lexicon",
    "apps.tastings",
    "apps.journal",
    "apps.public",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Populates request.htmx, which views use to decide between a full page
    # and a fragment response.
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                # Exposes SITE_NAME and RELEASE_VERSION to every template.
                "apps.public.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Site identity
# ---------------------------------------------------------------------------

SITE_NAME = config("SITE_NAME", default="Wineguide")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# Passwordless: a signed link by email, no password field anywhere (PRD §6.4).
# django.contrib.auth's default User is the model; the email address is both
# the username and the only thing we store about a person.

LOGIN_URL = "accounts:sign_in"
LOGIN_REDIRECT_URL = "tastings:start"
LOGOUT_REDIRECT_URL = "accounts:sign_in"

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="hello@wineguide.example")

# MAILERS, not EMAIL_BACKEND: Django 6 deprecated the old setting and removes
# it in 7.0. Development overrides this with the console backend.
MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend"},
}

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# Only user right now is the sign-in throttle, which needs to be shared across
# workers to mean anything. LocMemCache is per-process and therefore per-worker
# — fine for development and tests, wrong in production, where production.py
# overrides it.

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-gb"
LANGUAGES = [("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
