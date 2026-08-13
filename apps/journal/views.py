"""
apps/journal/views.py — Reading back what was tasted.

Ordinary server-rendered HTML with HTMX for the search-as-you-type list. This
is the half of the app where HTMX is exactly right: the interactions are
request-shaped, nothing is time-critical, and every one of them still works
with scripting off — the filter form is a real GET form, and the HTMX
attributes only change how the response is delivered.

Contrast `apps.tastings.views`, where a request per interaction would break
the product.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.enums import PHASE_ORDER, Phase, WineType
from apps.lexicon.inference import interpret, selected_codes
from apps.lexicon.models import Option, Question
from apps.tastings.models import TastingSession

from .filters import apply_filters, parse_filters, visible_sessions

PAGE_SIZE = 20

#: The only fields the journal lets you change, as
#: ``(name, label, input type, max length)``. One list, read by both the form
#: and the handler, so a field cannot appear on screen without being saved or
#: be saved without appearing. Observations are deliberately absent: the value
#: of a tasting note is what you thought at the time.
EDITABLE_FIELDS: tuple[tuple[str, str, str, int], ...] = (
    ("wine_name", "Wine", "text", 200),
    ("producer", "Producer", "text", 200),
    ("region", "Region", "text", 200),
    ("vintage", "Vintage", "number", 4),
    ("actual_grape", "Grape (revealed)", "text", 120),
    ("actual_origin", "Origin (revealed)", "text", 120),
)


@login_required
def journal_list(request: HttpRequest) -> HttpResponse:
    """List the taster's sessions, newest first.

    Returns just the results fragment to HTMX so typing in the search box
    does not reload the page around it; the same view serves the whole page
    to anything else, including a browser with JavaScript off.
    """
    filters = parse_filters(request.GET)
    sessions = apply_filters(visible_sessions(request.user), filters)
    page = Paginator(sessions, PAGE_SIZE).get_page(request.GET.get("page"))

    context = {
        "page": page,
        "filters": filters,
        "wine_types": WineType.choices,
        "qualities": _quality_options(),
    }
    template = (
        "journal/_results.html" if request.htmx else "journal/list.html"  # type: ignore[attr-defined]
    )
    return render(request, template, context)


def _quality_options() -> list[tuple[str, str]]:
    """Return the quality scale, for the filter dropdown.

    Read from the active lexicon rather than hard-coded, so a version that
    renames a rung does not leave the filter offering a value nothing has.
    """
    return list(
        Option.objects.filter(
            question__code="quality", question__lexicon__is_active=True
        )
        .order_by("order")
        .values_list("code", "label")
    )


@login_required
def detail(request: HttpRequest, uuid: str) -> HttpResponse:
    """Show one session in full, as it was recorded."""
    session: TastingSession = get_object_or_404(
        visible_sessions(request.user), uuid=uuid
    )
    # Interpreted against the lexicon the session was taken under, so a later
    # change to what a descriptor implies cannot rewrite an old note.
    groups, conclusions = interpret(session.lexicon, selected_codes(session.answers()))
    return render(
        request,
        "journal/detail.html",
        {
            "session": session,
            "phases": _rendered_phases(session),
            "origin_groups": groups,
            "conclusions": conclusions,
        },
    )


def _rendered_phases(session: TastingSession) -> list[dict[str, Any]]:
    """Resolve a session's answers into readable labels, phase by phase.

    Answers are stored as option codes against the lexicon version the
    session was taken under — never the active one — so a later correction to
    the wording cannot rewrite what someone recorded. An answer whose option
    has since been deleted falls back to its raw code rather than vanishing:
    a note that silently loses a line is worse than one with an ugly line.

    Args:
        session: The session to render.

    Returns:
        One entry per phase that has any answers.

    """
    answers = session.answers()
    skipped = {
        response.question_code
        for response in session.responses.all()
        if response.skipped
    }

    questions = list(
        Question.objects.filter(lexicon=session.lexicon).order_by("order", "id")
    )
    labels = dict(
        Option.objects.filter(question__lexicon=session.lexicon).values_list(
            "code", "label"
        )
    )

    phases: list[dict[str, Any]] = []
    for phase in PHASE_ORDER:
        rows: list[dict[str, Any]] = []
        for question in questions:
            if question.phase != phase:
                continue
            if question.code in skipped:
                rows.append({"prompt": question.prompt, "values": [], "skipped": True})
            elif question.code in answers:
                rows.append(
                    {
                        "prompt": question.prompt,
                        "values": [
                            labels.get(code, code) for code in answers[question.code]
                        ],
                        "skipped": False,
                    }
                )
        if rows:
            phases.append({"label": str(Phase(phase).label), "rows": rows})
    return phases


@login_required
def edit(request: HttpRequest, uuid: str) -> HttpResponse:
    """Correct or complete a session's wine details after the fact.

    Only the identity of the wine is editable — the name a taster fills in
    once they have checked the label, and the reveal after a blind tasting
    (PRD §6.2). The recorded observations are not editable here: the point of
    the journal is what you thought at the time.
    """
    session: TastingSession = get_object_or_404(
        visible_sessions(request.user), uuid=uuid
    )

    if request.method == "POST":
        for name, _label, kind, limit in EDITABLE_FIELDS:
            raw = request.POST.get(name, "").strip()
            if kind == "number":
                # A vintage that is not a number is dropped rather than
                # rejected. Someone correcting a producer's spelling should
                # not be stopped by what they typed in another box.
                setattr(session, name, int(raw) if raw.isdigit() else None)
            else:
                setattr(session, name, raw[:limit])
        session.save(
            update_fields=[name for name, _l, _k, _m in EDITABLE_FIELDS]
            + ["updated_at"]
        )
        return redirect(session.get_absolute_url())

    return render(
        request,
        "journal/edit.html",
        {
            "session": session,
            "fields": [
                (name, label, kind, getattr(session, name))
                for name, label, kind, _limit in EDITABLE_FIELDS
            ],
        },
    )


@require_POST
@login_required
def delete(request: HttpRequest, uuid: str) -> HttpResponse:
    """Delete a session.

    POST only, and no soft delete: PRD §8 promises a clear delete path, and a
    row that lingers invisibly is not one.

    Reachable from the detail page and from any row in the list. To HTMX it
    answers with the re-rendered list, so deleting a row from the listing
    leaves you in the listing rather than bouncing the page; anything else —
    including a browser with scripting off — gets the redirect it expects.
    The filters on the query string are preserved either way, so a delete
    made inside a search does not silently drop you back to everything.
    """
    session: TastingSession = get_object_or_404(
        visible_sessions(request.user), uuid=uuid
    )
    session.delete()
    if request.htmx:  # type: ignore[attr-defined]
        return journal_list(request)
    query = request.GET.urlencode()
    return redirect(f"{reverse('journal:list')}?{query}" if query else "journal:list")
