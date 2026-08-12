"""apps/core/apps.py — App configuration for shared building blocks."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Enums and helpers shared across apps. Holds no models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"
