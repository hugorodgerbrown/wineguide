"""
config/settings/development.py — Development-environment overrides.

Enables DEBUG, uses SQLite, and relaxes the security settings that would be
inappropriate locally. Also the settings module the test suite runs under.
"""

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,.ngrok-free.app",
).split(",")

# CSRF Origin checks require the scheme + host of the inbound request to appear
# here for POSTs to succeed, which matters when serving through a tunnel.
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://*.ngrok-free.app",
).split(",")

INTERNAL_IPS = ["127.0.0.1"]

# Sign-in links are printed to the console rather than sent. Reading the link
# out of the runserver log is the whole local sign-in flow.
MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        # Let a transiently-locked connection wait and retry rather than
        # erroring immediately — the Playwright suite shares the database
        # between the live-server thread and the test thread.
        "OPTIONS": {"timeout": 20},
    }
}
