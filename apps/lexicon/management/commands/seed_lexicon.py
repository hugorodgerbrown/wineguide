"""
apps/lexicon/management/commands/seed_lexicon.py — Publish a lexicon version.

Creates a `Lexicon` from `seed_data.QUESTIONS` and, unless told otherwise,
makes it the active one. Idempotent for a given version: re-running against an
existing version updates the wording in place rather than duplicating it, so a
typo fix is one command and does not orphan the sessions already recorded
against that version.

    manage.py seed_lexicon 2026.1
    manage.py seed_lexicon 2026.2 --no-activate

Publishing a NEW version rather than editing the current one is the right move
whenever the change would make an existing note read differently — a renamed
option, a removed descriptor, a reworded prompt. Sessions store the version
they were taken against, so old notes keep rendering as the taster saw them.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.lexicon.models import Inference, Lexicon, Option, Question
from apps.lexicon.seed_data import INFERENCES, QUESTIONS, OptionSpec


class Command(BaseCommand):
    """Seed or re-seed a lexicon version from `seed_data`."""

    help = "Create or update a lexicon version from apps/lexicon/seed_data.py"

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command's arguments."""
        # Positional, not --version: BaseCommand already defines --version
        # (it prints Django's), and argparse refuses the collision outright.
        parser.add_argument(
            "version",
            help="Version identifier to create or update, e.g. 2026.1.",
        )
        parser.add_argument(
            "--no-activate",
            action="store_true",
            help="Seed the version without making it the one new sessions use.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        """Create or update the version, then optionally activate it."""
        version: str = options["version"]
        activate: bool = not options["no_activate"]

        lexicon, created = Lexicon.objects.get_or_create(version=version)
        # Re-seeding replaces the question set wholesale. Editing in place
        # would leave any question dropped from seed_data behind in the
        # database, still being served, with nothing pointing at it.
        lexicon.questions.all().delete()
        lexicon.inferences.all().delete()

        for order, spec in enumerate(QUESTIONS):
            question = Question.objects.create(
                lexicon=lexicon,
                phase=spec["phase"],
                code=spec["code"],
                prompt=spec["prompt"],
                short_label=spec.get("short", ""),
                how_to_tell=spec.get("how", ""),
                why_it_matters=spec.get("why", ""),
                control=spec["control"],
                wine_types=list(spec.get("wine_types", [])),
                order=order,
            )
            self._create_options(question, spec.get("options", []))

        for order, inference in enumerate(INFERENCES):
            Inference.objects.create(
                lexicon=lexicon,
                code=inference["code"],
                label=inference["label"],
                explanation=inference["explanation"],
                order=order,
            )

        if activate:
            # Deactivate first: the partial unique index refuses a second
            # active row, so flipping the new one on while the old is still
            # active would fail.
            Lexicon.objects.exclude(pk=lexicon.pk).update(is_active=False)
            lexicon.is_active = True
            lexicon.save(update_fields=["is_active"])

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} lexicon {version}: "
                f"{lexicon.questions.count()} questions, "
                f"{Option.objects.filter(question__lexicon=lexicon).count()} options, "
                f"{lexicon.inferences.count()} inferences"
                f"{' (active)' if activate else ''}"
            )
        )

    def _create_options(
        self,
        question: Question,
        specs: list[OptionSpec],
        parent: Option | None = None,
    ) -> None:
        """Create a question's options, recursing one level into children."""
        for order, spec in enumerate(specs):
            option = Option.objects.create(
                question=question,
                parent=parent,
                code=spec["code"],
                label=spec["label"],
                guidance=spec.get("guidance", ""),
                origin=spec.get("origin", ""),
                implies=spec.get("implies", ""),
                swatch=spec.get("swatch", ""),
                wine_types=list(spec.get("wine_types", [])),
                order=order,
            )
            self._create_options(question, spec.get("children", []), parent=option)
