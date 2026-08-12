"""
apps/public/views.py — Public site views.

``home`` renders the homepage. ``wine_pick`` re-renders just the pick panel,
and is the one endpoint with two response shapes: HTMX asks for the fragment
and swaps it in place, while a plain browser request (no JS, or a bookmarked
URL) gets the whole page back. The no-JS path is not a fallback bolted on
afterwards — it is the same view, and the template's control is an ordinary
link that HTMX intercepts when it is available.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .wines import wine_at

PANEL_TEMPLATE = "public/_wine_panel.html"
HOME_TEMPLATE = "public/home.html"


def _pick_index(request: HttpRequest) -> int:
    """Read the requested rotation index from the query string.

    Anything unparseable is treated as 0 rather than a 400: the index is a
    position in a rotation, not an identifier, so there is no such thing as a
    "wrong" one — see ``wines.wine_at``, which wraps.
    """
    try:
        return int(request.GET.get("index", 0))
    except ValueError:
        return 0


def _pick_context(index: int) -> dict[str, object]:
    """Build the context shared by the full page and the fragment."""
    return {
        "wine": wine_at(index),
        "next_index": index + 1,
    }


def home(request: HttpRequest) -> HttpResponse:
    """Render the homepage, including the first wine pick."""
    return render(request, HOME_TEMPLATE, _pick_context(_pick_index(request)))


def wine_pick(request: HttpRequest) -> HttpResponse:
    """Render the next wine pick — as a fragment for HTMX, else a full page."""
    context = _pick_context(_pick_index(request))
    template = PANEL_TEMPLATE if request.htmx else HOME_TEMPLATE  # type: ignore[attr-defined]
    return render(request, template, context)
