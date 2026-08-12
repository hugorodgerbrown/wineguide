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


@login_required
def start(request: HttpRequest) -> HttpResponse:
    """Render the session shell.

    The bootstrap context is deliberately small — styles, and the endpoints
    the client will call. Everything else the client needs it fetches once as
    a lexicon payload and then caches, so this page is cheap enough for the
    service worker to keep and serve offline.
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
            }
        },
    )
