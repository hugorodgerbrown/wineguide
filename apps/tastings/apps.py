"""apps/tastings/apps.py — App configuration for the tasting record."""

from django.apps import AppConfig


class TastingsConfig(AppConfig):
    """Sessions, their answers, and the deduction at the end."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tastings"
    verbose_name = "Tastings"
