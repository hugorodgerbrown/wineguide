"""
apps/core/enums.py — Vocabulary shared by the lexicon and the tasting record.

These live in `core` rather than in either app because both need them and
neither owns them: the lexicon describes questions *per* wine type and phase,
and a tasting session records answers *against* them. A value here is part of
the wire format between the server and the client state machine, so the string
values are API surface — change one and you invalidate every stored response
and every cached client payload.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class WineType(models.TextChoices):
    """The wine styles a session can be started for.

    The style decides which questions and options apply: "garnet" is not a
    Chardonnay colour, and tannin is not a question worth asking about a
    Riesling (PRD §6.1).
    """

    STILL_WHITE = "still_white", _("Still white")
    STILL_RED = "still_red", _("Still red")
    ROSE = "rose", _("Rosé")
    SPARKLING = "sparkling", _("Sparkling")
    FORTIFIED = "fortified", _("Fortified")


class Phase(models.TextChoices):
    """The four phases of the tasting sequence, in the order they are taken."""

    LOOK = "look", _("Look")
    SMELL = "smell", _("Smell")
    TASTE = "taste", _("Taste")
    CONCLUDE = "conclude", _("Conclude")


#: Phase running order. `TextChoices` has no inherent ordering and the database
#: stores the string, so anything that needs the sequence — sorting questions,
#: driving the progress indicator, deciding what "next" means — reads it here.
PHASE_ORDER: tuple[str, ...] = (
    Phase.LOOK,
    Phase.SMELL,
    Phase.TASTE,
    Phase.CONCLUDE,
)

#: Soft time budget per phase, in seconds, from PRD §5. These pace the session;
#: they never force it. The client shows elapsed time against the budget and
#: nudges when it is spent, but the taster advances by tapping — nothing
#: auto-submits, because rushing a beginner defeats the point (PRD §5, §7).
PHASE_SECONDS: dict[str, int] = {
    Phase.LOOK: 45,
    Phase.SMELL: 90,
    Phase.TASTE: 150,
    Phase.CONCLUDE: 90,
}


class Control(models.TextChoices):
    """How a question is answered, and therefore how the client renders it.

    SINGLE and MULTI are chip grids; SCALE is an ordered segmented control
    whose options run low to high, so the client can render it as a track
    rather than as loose chips.
    """

    SINGLE = "single", _("Pick one")
    MULTI = "multi", _("Pick any")
    SCALE = "scale", _("Scale, low to high")


class SessionStatus(models.TextChoices):
    """Lifecycle of a tasting session.

    IN_PROGRESS covers both a live session and one the taster walked away
    from — nothing is lost either way, because the client persists locally on
    every tap (PRD §6.2). A session becomes ABANDONED only when the taster
    says so; the app never decides that on their behalf.
    """

    IN_PROGRESS = "in_progress", _("In progress")
    COMPLETED = "completed", _("Completed")
    ABANDONED = "abandoned", _("Abandoned")


def phase_index(phase: str) -> int:
    """Return the running-order position of ``phase``.

    Args:
        phase: A `Phase` value.

    Returns:
        Its index in `PHASE_ORDER`.

    Raises:
        ValueError: If the phase is not a known one.

    """
    try:
        return PHASE_ORDER.index(phase)
    except ValueError as exc:
        raise ValueError(f"Unknown phase: {phase!r}") from exc
