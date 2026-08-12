"""apps/lexicon/admin.py — Admin for correcting vocabulary without a deploy."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from .models import Lexicon, Option, Question


class OptionInline(admin.TabularInline):
    """Options edited alongside their question."""

    model = Option
    extra = 0
    fields = ("order", "code", "label", "parent", "swatch", "wine_types")
    ordering = ("order", "id")


@admin.register(Lexicon)
class LexiconAdmin(admin.ModelAdmin):
    """A published vocabulary set."""

    list_display = ("version", "is_active", "question_count", "created_at")
    list_filter = ("is_active",)
    search_fields = ("version", "notes")
    readonly_fields = ("created_at",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Lexicon]:
        """Annotate the question count so the list view stays one query."""
        queryset: QuerySet[Lexicon] = super().get_queryset(request)
        return queryset.annotate(_questions=Count("questions"))

    @admin.display(description="Questions", ordering="_questions")
    def question_count(self, obj: Lexicon) -> int:
        """Return how many questions this version holds."""
        return int(getattr(obj, "_questions", 0))


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """One prompt, with its options inline."""

    list_display = ("prompt", "lexicon", "phase", "code", "control", "order")
    list_filter = ("lexicon", "phase", "control")
    search_fields = ("code", "prompt", "help_text")
    ordering = ("lexicon", "order")
    inlines = [OptionInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):  # type: ignore[no-untyped-def]
        """Limit an option's parent choices to the same question.

        `Option.clean` rejects a cross-question parent, but a select listing
        every option in the database is unusable long before it is wrong.
        """
        if db_field.name == "parent":
            kwargs["queryset"] = Option.objects.select_related("question")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
