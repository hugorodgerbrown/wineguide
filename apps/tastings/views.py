"""
apps/tastings/views.py — The guided session.

One URL, one page. Everything from picking a wine style to the closing summary
happens inside it, driven by the client state machine in
`static/js/session/`. That is not a stylistic preference: PRD §8 asks for
phase transitions under 200ms and a session that survives the venue wifi
dropping between Look and Smell, and a page navigation per tap can deliver
neither.

The server's job here is to render the shell, hand over the URLs the client
needs, and get out of the way. It does not know which phase anyone is on.

This is the one part of the app that requires JavaScript. A guided, timed,
offline-capable sequence cannot be delivered without it. Everything else —
the journal, sign-in — is ordinary server-rendered HTML and works with
scripting off.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from apps.core.enums import WineType


def _shell(request: HttpRequest, *, resume: bool) -> HttpResponse:
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
