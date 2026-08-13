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


class Axis(models.TextChoices):
    """What a question measures, and therefore what mark its options carry.

    From the design system's `guidelines/sensory-axes.html`: every observed
    scale is one sense reporting one geometry. Sight reports colour, smell
    reports how far the wine carries, the taste receptors report quantity and
    where it lands, the trigeminal nerve reports weight, heat and friction,
    and the finish reports time. Five modalities, and the geometry is what the
    mark draws.

    The axis rather than the question decides the mark, so a question added
    later inherits an existing one and nothing new has to be drawn. Tannin and
    mousse are both GRAIN because both are friction; sweetness is FILL because
    it is a quantity on the tongue.

    Blank is meaningful and is the default: it means this question carries no
    mark. Everything in Conclude is blank — "faulty" to "outstanding" is
    ordered, but it is a judgement the taster arrives at rather than a
    sensation they receive, so there is no geometry for a mark to illustrate.
    Categorical questions are blank for the same reason: no ramp runs through
    "clear" and "hazy".
    """

    CARRY = "carry", _("Distance the sensation travels")
    BURST = "burst", _("How much arrives at once")
    FILL = "fill", _("Quantity on the tongue")
    SPREAD = "spread", _("How far across the mouth it reaches")
    RISE = "rise", _("Warmth climbing from the throat")
    WEIGHT = "weight", _("Thickness — how heavy it feels")
    GRAIN = "grain", _("Friction — grip and texture")
    LENGTH = "length", _("Time it lasts after swallowing")
    SWATCH = "swatch", _("Hue and depth — the one coloured mark")


class AromaOrigin(models.TextChoices):
    """Where a smell or flavour came from.

    This is the framework the app exists to teach, and the taster is not
    expected to know it — that is the point. They record that they smell
    brioche; the app is what says brioche is secondary and means time on the
    lees. Asking someone to file their own descriptors under
    primary/secondary/tertiary is asking them to have already learned the
    thing they came to learn.

    Carried on the option, so the sorting is data rather than logic.
    """

    PRIMARY = "primary", _("From the grape")
    SECONDARY = "secondary", _("From the winemaking")
    TERTIARY = "tertiary", _("From age")


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
