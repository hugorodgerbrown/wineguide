"""
apps/lexicon/payload.py — The lexicon as the client receives it.

This module is the contract between the server and the client state machine.
The client fetches one payload when a session starts, caches it, and then runs
the entire tasting from memory: no request is made between tapping an answer
and seeing the next prompt, which is what keeps phase transitions under the
200ms PRD §8 asks for, and what lets a session continue when the venue wifi
drops between Look and Smell.

Everything the client needs is therefore in here — prompts, options, controls,
help text, phase labels and time budgets. The client knows nothing about wine
and never asks the server a follow-up question.

Shape:

    {
      "version": "2026.1",
      "wine_type": "still_red",
      "phases": [
        {
          "code": "look",
          "label": "Look",
          "seconds": 45,
          "questions": [
            {
              "code": "clarity",
              "prompt": "Is it clear or hazy?",
              "help": "…",
              "control": "single",
              "options": [
                {"code": "clear", "label": "Clear", "swatch": "", "children": []}
              ]
            }
          ]
        }
      ]
    }

`children` carries the one level of nesting the lexicon allows: a category the
taster opens, holding the descriptors they pick.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Prefetch

from apps.core.enums import PHASE_ORDER, PHASE_SECONDS, Phase

from .models import Lexicon, Option, Question


def _one_option(option: Option) -> dict:
    """Serialise a single option, without its children."""
    return {
        "code": option.code,
        "label": option.label,
        # How to know it is this one and not the one beside it. The whole
        # difficulty of a scale question lives in this string.
        "guidance": option.guidance,
        # The tags the client's inference module reads to sort descriptors and
        # name the processes they point at.
        "origin": option.origin,
        "implies": option.implies,
        "swatch": option.swatch,
    }


def _option_payload(option: Option, children: list[Option], wine_type: str) -> dict:
    """Serialise one option and the descriptors beneath it."""
    return {
        **_one_option(option),
        "children": [
            _one_option(child) for child in children if child.applies_to(wine_type)
        ],
    }


def _question_payload(question: Question, wine_type: str) -> dict:
    """Serialise one question with the options that apply to ``wine_type``."""
    applicable = [o for o in question.options.all() if o.applies_to(wine_type)]
    children_by_parent: dict[int, list[Option]] = {}
    for option in applicable:
        if option.parent_id is not None:
            children_by_parent.setdefault(option.parent_id, []).append(option)

    return {
        "code": question.code,
        "prompt": question.prompt,
        # One or two words, for the navigation rail.
        "short": question.nav_label,
        # Shown on the question itself — the physical instruction.
        "how": question.how_to_tell,
        # Available on tap — what the answer says about the wine.
        "why": question.why_it_matters,
        "control": question.control,
        "options": [
            _option_payload(option, children_by_parent.get(option.id, []), wine_type)
            for option in applicable
            if option.parent_id is None
        ],
    }


def build_payload(lexicon: Lexicon, wine_type: str) -> dict[str, Any]:
    """Build the whole client payload for one lexicon and one wine style.

    Two queries regardless of size: the questions, and their options
    prefetched. Filtering by wine type happens in Python — see
    `models.applies_to` for why.

    A phase with no applicable questions is dropped rather than sent empty, so
    the client's progress indicator never counts a phase the taster will not
    be shown.

    Args:
        lexicon: The vocabulary set to serialise.
        wine_type: A `WineType` value.

    Returns:
        The payload described in this module's docstring.

    """
    questions = (
        Question.objects.filter(lexicon=lexicon)
        .prefetch_related(
            Prefetch("options", queryset=Option.objects.order_by("order", "id"))
        )
        .order_by("order", "id")
    )
    applicable = [q for q in questions if q.applies_to(wine_type)]

    phases = []
    for phase in PHASE_ORDER:
        in_phase = [q for q in applicable if q.phase == phase]
        if not in_phase:
            continue
        phases.append(
            {
                # str() rather than the enum member: this is wire format, and
                # a caller that json.dumps it should not be relying on
                # TextChoices happening to subclass str.
                "code": str(phase),
                "label": str(Phase(phase).label),
                "seconds": PHASE_SECONDS[phase],
                "questions": [_question_payload(q, wine_type) for q in in_phase],
            }
        )

    return {
        "version": lexicon.version,
        "wine_type": wine_type,
        "phases": phases,
        # The conclusions the client can draw offline. Sent with the questions
        # rather than fetched at the end, because the end of a session is
        # exactly when the network is least likely to be there.
        "inferences": [
            {
                "code": inference.code,
                "label": inference.label,
                "explanation": inference.explanation,
            }
            for inference in lexicon.inferences.all()
        ],
    }
