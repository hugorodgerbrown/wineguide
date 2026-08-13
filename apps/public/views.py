"""
apps/public/views.py — The landing page.

One view, one template, no JavaScript. The page is addressed to someone
deciding whether to learn to taste, so its whole job is to say what the app
teaches and how — the four-phase sequence, and the two things that separate it
from a form you fill in once you already know the answers.

The phase blurbs are built from `Phase` rather than written into the template,
so the sequence advertised here cannot drift from the sequence the session
actually runs.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from apps.core.enums import PHASE_ORDER, Phase

HOME_TEMPLATE = "public/home.html"

#: One line per phase, keyed by the enum so a phase cannot be advertised that
#: the session does not run — or be added to the session and go unmentioned.
PHASE_BLURBS: dict[str, Promise] = {
    Phase.LOOK: _(
        "Clarity, depth and colour, against something white. The rim tells you "
        "more than the middle."
    ),
    Phase.SMELL: _(
        "How much it gives, and what of. You pick the smells you recognise; the "
        "app works out where they came from."
    ),
    Phase.TASTE: _(
        "Sweetness, acidity, tannin, alcohol, body and finish — the structure, "
        "one sensation at a time, each with the way to feel for it."
    ),
    Phase.CONCLUDE: _(
        "How good, how ready, and your guess at the grape. Say how sure you "
        "are, then find out."
    ),
}


def home(request: HttpRequest) -> HttpResponse:
    """Render the landing page."""
    return render(
        request,
        HOME_TEMPLATE,
        {
            "phases": [
                {"label": str(Phase(code).label), "blurb": PHASE_BLURBS[code]}
                for code in PHASE_ORDER
            ]
        },
    )
