"""apps/journal/apps.py — App configuration for the tasting journal."""

from django.apps import AppConfig


class JournalConfig(AppConfig):
    """Reading, searching and editing past sessions.

    Owns no models — it is a view layer over `apps.tastings`. The split is
    deliberate: the session is a real-time client-side thing with hard latency
    requirements, and the journal is ordinary server-rendered HTML. Keeping
    them apart keeps that distinction visible in the file tree.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.journal"
    verbose_name = "Journal"
