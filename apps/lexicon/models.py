"""
apps/lexicon/models.py — The versioned vocabulary a tasting session is driven by.

PRD §6.3 asks for the vocabulary to be structured, versioned data rather than
per-screen strings, so terminology can be corrected or extended without a code
change. That is what this app is: the client renders whatever the server sends
and knows nothing about wine.

Three models:

    Lexicon   one published vocabulary set, e.g. "2026.1". Exactly one is
              active; a session records which one it was taken against, so a
              later correction never rewrites history.
    Question  one prompt, in one phase, with a control type and the wine
              types it applies to.
    Option    one answer chip. Options nest one level — a broad category
              (citrus fruit) holding specific descriptors (grapefruit, lemon,
              lime) — because that is how the method teaches a taster to
              narrow in (PRD §6.3).

On terminology: the four-phase sequence and the primary/secondary/tertiary
framework are the industry-standard teaching method and free to build on. The
descriptor wording seeded in `seed_lexicon` is written for this app rather than
transcribed from any awarding body's copyrighted lists — see the IP note in
PRD §11.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.enums import Control, Phase, WineType, phase_index


class LexiconQuerySet(models.QuerySet["Lexicon"]):
    """Queryset helpers for `Lexicon`."""

    def active(self) -> Lexicon:
        """Return the single active lexicon.

        Returns:
            The active lexicon.

        Raises:
            Lexicon.DoesNotExist: If no lexicon is active. This is a
                deployment error, not a user error — an app with no
                vocabulary cannot run a session — so it is left to surface as
                a 500 rather than being papered over with a default.

        """
        return self.get(is_active=True)


class Lexicon(models.Model):
    """One published vocabulary set.

    Versioning is what lets the wording be corrected without falsifying old
    notes: a session stores the lexicon it was taken against, so its answers
    keep rendering with the labels the taster actually saw.
    """

    version = models.CharField(
        _("version"),
        max_length=32,
        unique=True,
        help_text=_("Identifier for this vocabulary set, e.g. 2026.1."),
    )
    notes = models.TextField(
        _("notes"),
        blank=True,
        help_text=_("What changed in this version, and why."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=False,
        help_text=_("The version new sessions are started against. Only one."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    objects = LexiconQuerySet.as_manager()

    class Meta:
        verbose_name = _("lexicon")
        verbose_name_plural = _("lexicons")
        ordering = ("-created_at",)
        constraints = [
            # Partial unique index on a constant: every active row collides on
            # the same key, so the database refuses a second one. Enforcing it
            # here rather than in save() means a data migration, a fixture load
            # and the admin are all held to it.
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="lexicon_only_one_active",
            ),
        ]

    def __str__(self) -> str:
        """Return the version, marked when it is the active one."""
        return f"{self.version}{' (active)' if self.is_active else ''}"


def applies_to(wine_types: list[str], wine_type: str) -> bool:
    """Return whether a row scoped to ``wine_types`` applies to ``wine_type``.

    An empty list means "every style", which is the common case — most of the
    sequence is the same whatever is in the glass. Only where the style
    genuinely changes the question (colour, tannin, bubbles) does a row name
    its styles.

    This is a Python predicate rather than a queryset filter on purpose. The
    JSONField ``contains`` lookup is unsupported on SQLite, which is what
    development and the test suite run on, so a database-side filter would
    work in production and raise locally. The lexicon is small and is read
    once per session, so filtering the loaded rows costs nothing.

    Args:
        wine_types: The row's declared styles; empty for "all".
        wine_type: The style being tasted.

    Returns:
        True if the row should be shown.

    """
    return not wine_types or wine_type in wine_types


class Question(models.Model):
    """One prompt in one phase of the sequence."""

    lexicon = models.ForeignKey(
        Lexicon,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("lexicon"),
    )
    phase = models.CharField(_("phase"), max_length=16, choices=Phase.choices)
    code = models.SlugField(
        _("code"),
        max_length=64,
        help_text=_("Stable identifier stored on every response, e.g. acidity."),
    )
    prompt = models.CharField(
        _("prompt"),
        max_length=120,
        help_text=_("Readable in under three seconds, at the table."),
    )
    help_text = models.TextField(
        _("help text"),
        blank=True,
        help_text=_("The optional 'why this matters' note. A hint, not a lesson."),
    )
    control = models.CharField(
        _("control"), max_length=16, choices=Control.choices, default=Control.SINGLE
    )
    wine_types = models.JSONField(
        _("wine types"),
        default=list,
        blank=True,
        help_text=_("Styles this applies to. Empty means all of them."),
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        verbose_name = _("question")
        verbose_name_plural = _("questions")
        ordering = ("phase", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["lexicon", "code"], name="question_code_unique_per_lexicon"
            ),
        ]

    def __str__(self) -> str:
        """Return the phase and prompt."""
        return f"{self.get_phase_display()}: {self.prompt}"

    def clean(self) -> None:
        """Reject wine types that are not real styles.

        `wine_types` is a JSON list, so `choices` cannot police it and a typo
        would otherwise fail silently — the question would simply never appear
        for any style, which is invisible until someone runs a session.
        """
        super().clean()
        unknown = set(self.wine_types or []) - set(WineType.values)
        if unknown:
            raise ValidationError(
                {"wine_types": _("Unknown wine types: %s") % ", ".join(sorted(unknown))}
            )

    @property
    def phase_index(self) -> int:
        """Return this question's phase position in the running order."""
        return phase_index(self.phase)

    def applies_to(self, wine_type: str) -> bool:
        """Return whether this question is asked for ``wine_type``."""
        return applies_to(self.wine_types, wine_type)


class Option(models.Model):
    """One selectable answer.

    Options nest exactly one level deep. A parent is a category the taster
    opens; its children are the descriptors they pick. Anything deeper would
    be more taxonomy than someone holding a glass can navigate.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name=_("question"),
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("parent"),
        help_text=_("The category this descriptor sits under, if any."),
    )
    code = models.SlugField(_("code"), max_length=64)
    label = models.CharField(_("label"), max_length=80)
    swatch = models.CharField(
        _("swatch"),
        max_length=7,
        blank=True,
        help_text=_(
            "Hex colour for appearance options. Always shown beside the label, "
            "never instead of it — the colour is decoration, the word is the "
            "answer."
        ),
    )
    wine_types = models.JSONField(
        _("wine types"),
        default=list,
        blank=True,
        help_text=_("Styles this applies to. Empty means all of them."),
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        verbose_name = _("option")
        verbose_name_plural = _("options")
        ordering = ("question", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["question", "code"], name="option_code_unique_per_question"
            ),
        ]

    def __str__(self) -> str:
        """Return the label, prefixed by its category when it has one."""
        return f"{self.parent.label} › {self.label}" if self.parent else self.label

    def clean(self) -> None:
        """Reject unknown wine types, cross-question parents and deep nesting."""
        super().clean()
        unknown = set(self.wine_types or []) - set(WineType.values)
        if unknown:
            raise ValidationError(
                {"wine_types": _("Unknown wine types: %s") % ", ".join(sorted(unknown))}
            )
        parent = self.parent
        if parent is None:
            return
        if parent.question_id != self.question_id:
            raise ValidationError(
                {"parent": _("A category must belong to the same question.")}
            )
        if parent.parent_id is not None:
            raise ValidationError(
                {"parent": _("Options nest one level: a category and its descriptors.")}
            )

    def applies_to(self, wine_type: str) -> bool:
        """Return whether this option is offered for ``wine_type``."""
        return applies_to(self.wine_types, wine_type)
