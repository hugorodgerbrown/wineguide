"""apps/tastings/admin.py — Read-mostly admin over the tasting record."""

from __future__ import annotations

from django.contrib import admin

from .models import PhaseResponse, TastingSession


class PhaseResponseInline(admin.TabularInline):
    """A session's answers, shown alongside it."""

    model = PhaseResponse
    extra = 0
    fields = ("phase", "question_code", "values", "skipped")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        """Answers are written by the taster, never by staff.

        Editing someone's tasting note from the admin would corrupt the record
        the whole product exists to build.
        """
        return False


@admin.register(TastingSession)
class TastingSessionAdmin(admin.ModelAdmin):
    """One sitting with one wine."""

    list_display = (
        "display_name",
        "user",
        "wine_type",
        "status",
        "quality",
        "started_at",
    )
    list_filter = ("status", "wine_type", "lexicon", "tasted_blind")
    search_fields = ("wine_name", "producer", "region", "user__email")
    date_hierarchy = "started_at"
    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
        "client_updated_at",
        "quality",
        "guessed_grape",
        "colour_hex",
    )
    inlines = [PhaseResponseInline]

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        """Select the joins the list display reads, to keep it one query."""
        return super().get_queryset(request).select_related("user", "lexicon")
