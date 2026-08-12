"""apps/lexicon/apps.py — App configuration for the tasting vocabulary."""

from django.apps import AppConfig


class LexiconConfig(AppConfig):
    """The versioned question-and-option set that drives a tasting session."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.lexicon"
    verbose_name = "Lexicon"
