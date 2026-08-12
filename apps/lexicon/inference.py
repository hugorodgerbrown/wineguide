"""
apps/lexicon/inference.py — Turning descriptors into conclusions.

The taster records that they smell brioche, butter and vanilla. This is what
turns that into "secondary aromas, from the winemaking — time on the lees,
malolactic conversion, oak", which is the thing they came to learn and the
thing they should not have been asked to already know.

All of it is driven by the `origin` and `implies` tags on `Option`, so adding
a descriptor or changing what it points at is a lexicon edit, not a code
change.

There is a sibling implementation in `static/js/session/session_inference.js`,
because the closing summary has to work with no network (PRD §8) and the
journal is server-rendered. Both read the same tags out of the same lexicon,
and both are tested against the same cases. If you change the rule here,
change it there — `tests/lexicon/test_inference.py` and
`tests/js/test_session_inference.js` are deliberately parallel.

The rule is deliberately simple: an inference fires if any descriptor tagged
with it was chosen. No thresholds, no weighting, no confidence score. "You
found butter, which usually means malolactic conversion" is a true and useful
sentence on one descriptor, and a percentage would imply a precision this does
not have.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.core.enums import AromaOrigin
from apps.lexicon.models import Inference, Lexicon, Option


@dataclass(frozen=True, slots=True)
class OriginGroup:
    """The descriptors a taster found from one origin."""

    origin: str
    label: str
    descriptors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Conclusion:
    """A process the descriptors point at, and why."""

    code: str
    label: str
    explanation: str
    #: The descriptors that fired it, so the app can show its working rather
    #: than pronouncing. "Because you found butter and cream" is the teaching
    #: half; the label alone is just another thing to memorise.
    evidence: tuple[str, ...]


def _descriptor_options(lexicon: Lexicon) -> list[Option]:
    """Return every option in ``lexicon`` that carries an origin or an implication."""
    return list(
        Option.objects.filter(question__lexicon=lexicon)
        .exclude(origin="", implies="")
        .select_related("question")
        .order_by("question__order", "order")
    )


def interpret(
    lexicon: Lexicon, selected_codes: set[str]
) -> tuple[list[OriginGroup], list[Conclusion]]:
    """Sort the chosen descriptors by origin and say what they imply.

    Args:
        lexicon: The version the session was taken against — never the active
            one, or an old note would be reinterpreted under new rules.
        selected_codes: Every option code the taster picked, across all
            questions. Aroma and flavour share a vocabulary, so a descriptor
            found on both the nose and the palate is one entry here.

    Returns:
        The origin groups present, in primary/secondary/tertiary order, and
        the conclusions they support, in the lexicon's own order. Both empty
        when nothing was recorded.

    """
    options = [o for o in _descriptor_options(lexicon) if o.code in selected_codes]

    # De-duplicated by label: the same descriptor chosen on the nose and again
    # on the palate is one finding, not two. Sorted for a stable reading order.
    by_origin: dict[str, set[str]] = {}
    by_inference: dict[str, set[str]] = {}
    for option in options:
        if option.origin:
            by_origin.setdefault(option.origin, set()).add(option.label)
        if option.implies:
            by_inference.setdefault(option.implies, set()).add(option.label)

    groups = [
        OriginGroup(
            origin=origin,
            label=str(AromaOrigin(origin).label),
            descriptors=tuple(sorted(by_origin[origin])),
        )
        for origin in AromaOrigin.values
        if origin in by_origin
    ]

    conclusions = [
        Conclusion(
            code=inference.code,
            label=inference.label,
            explanation=inference.explanation,
            evidence=tuple(sorted(by_inference[inference.code])),
        )
        for inference in lexicon.inferences.all()
        if inference.code in by_inference
    ]

    return groups, conclusions


def selected_codes(answers: dict[str, list[str]]) -> set[str]:
    """Flatten a session's answers into the set of codes it chose.

    Args:
        answers: As returned by `TastingSession.answers`.

    Returns:
        Every option code selected, across every question.

    """
    return {code for values in answers.values() for code in values}


__all__ = [
    "Conclusion",
    "Inference",
    "OriginGroup",
    "interpret",
    "selected_codes",
]
