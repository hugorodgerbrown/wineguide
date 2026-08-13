"""
apps/tastings/views.py — The guided session.

One URL, one page. Everything from picking a wine style to the closing summary
happens inside it, driven by the client state machine in
`static/js/session/`. That is not a stylistic preference: PRD §8 asks for
phase transitions under 200ms and a session that survives the venue wifi
dropping between Look and Smell, and a page navigation per tap can deliver
neither.

Three ways in, and the difference between them is the server's to decide,
because each is a navigation the taster just made:

    /taste/          resume an unfinished tasting, or start one
    /taste/new/      always start one
    /taste/<uuid>/   reopen a stored one and change any answer

The server's job here is to render the shell, hand over the URLs the client
needs, and get out of the way. It does not know which phase anyone is on.

This is the one part of the app that requires JavaScript. A guided, timed,
offline-capable sequence cannot be delivered without it. Everything else —
the journal, sign-in — is ordinary server-rendered HTML and works with
scripting off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.enums import WineType
from apps.tastings.models import TastingSession

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


def _client_state(session: TastingSession) -> dict[str, Any]:
    """Rebuild the client's session state from a stored tasting.

    The shape has to match `createSession` in session_core.js exactly — the
    state machine is handed this and carries on as if it had built it itself.
    The cursor starts at the end, on the summary, because someone reopening a
    note came to change one answer rather than to walk the sequence again;
    every question is one tap away from there.

    `elapsed` is deliberately empty and `phaseEnteredAt` null. The phase clock
    paces a live tasting; re-running it against a note recorded last month
    would only tell the taster they are over budget on a wine they have
    already drunk.
    """
    return {
        "uuid": str(session.uuid),
        "lexiconVersion": session.lexicon.version,
        "wineType": session.wine_type,
        "wine": {
            "name": session.wine_name,
            "producer": session.producer,
            "region": session.region,
            "vintage": session.vintage or "",
            "blind": session.tasted_blind,
        },
        "actual": {
            "grape": session.actual_grape,
            "origin": session.actual_origin,
        },
        "status": session.status,
        "startedAt": session.started_at.isoformat(),
        "updatedAt": session.client_updated_at.isoformat(),
        "answers": {
            response.question_code: {
                "values": list(response.values),
                "skipped": response.skipped,
            }
            for response in session.responses.all()
        },
        "elapsed": {},
        "phaseEnteredAt": None,
    }


def _shell(
    request: HttpRequest,
    *,
    resume: bool,
    session: TastingSession | None = None,
) -> HttpResponse:
    """Render the session shell.

    The bootstrap context is deliberately small — styles, the endpoints the
    client will call, and whether it may pick up where it left off.
    Everything else the client needs it fetches once as a lexicon payload and
    then caches, so this page is cheap enough for the service worker to keep
    and serve offline.
    """
    return render(
        request,
        "tastings/session.html",
        {
            "bootstrap": {
                "wine_types": [
                    {"value": value, "label": str(label)}
                    for value, label in WineType.choices
                ],
                "lexicon_url": reverse(
                    "tastings_api:lexicon", kwargs={"wine_type": "WINE_TYPE"}
                ),
                "sync_url": reverse("tastings_api:sync"),
                "journal_url": reverse("journal:list"),
                "new_url": reverse("tastings:start_new"),
                # The server decides this, not the client. "Take me somewhere
                # new" is a navigation, and a navigation that lands you back
                # in a half-finished tasting is the app overriding a choice
                # the taster just made.
                "resume": resume,
                # A tasting being reopened, handed over whole. Absent for the
                # other two entry points, where the client owns the state.
                "session": _client_state(session) if session else None,
                # Reopening pins the lexicon to the version the note was
                # taken against. A note recorded before a question was added
                # must not come back with a gap in it, and one recorded
                # before wording changed must not read differently now.
                "lexicon_version": session.lexicon.version if session else "",
            }
        },
    )


@login_required
def start(request: HttpRequest) -> HttpResponse:
    """Render the session, resuming an unfinished one if there is one."""
    return _shell(request, resume=True)


@login_required
def start_new(request: HttpRequest) -> HttpResponse:
    """Render the session, always starting from the setup screen.

    An unfinished tasting is not discarded — it stays in the journal, and it
    is still on the client. It is simply not what this URL is for.
    """
    return _shell(request, resume=False)


@login_required
def reopen(request: HttpRequest, uuid: str) -> HttpResponse:
    """Reopen a stored tasting so any answer can be changed.

    The journal can edit what the bottle was; only the session can edit what
    the taster thought of it, because only the session knows how to ask. So
    "change an answer" is this page rather than a form: the same rail, the
    same guidance, the same one-question-at-a-time.

    Scoped to the signed-in taster through the same queryset the journal uses
    — a session uuid is unguessable, but that is not a reason to serve one to
    whoever asks.
    """
    # `login_required` has already ruled out AnonymousUser; the annotation on
    # `request.user` cannot know that.
    user = cast("AbstractBaseUser", request.user)
    session = get_object_or_404(
        TastingSession.objects.for_user(user).select_related("lexicon"),
        uuid=uuid,
    )
    return _shell(request, resume=False, session=session)
