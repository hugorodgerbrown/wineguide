"""apps/public/apps.py — App configuration for the public site."""

from django.apps import AppConfig


class PublicConfig(AppConfig):
    """The public-facing site: homepage and its fragments."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.public"
    verbose_name = "Public site"
