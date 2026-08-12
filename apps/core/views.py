"""
apps/core/views.py — The two views that have to live at the site root.

A service worker can only control pages at or below its own path, so
``/static/js/sw.js`` could only ever control ``/static/…``. It has to be
served from ``/sw.js``, which means a view rather than a static file.

Serving it through Django also lets the cache version be substituted from the
release version at request time. The alternative — a constant in the file that
someone bumps by hand on each deploy — is a step that gets forgotten exactly
once, and then every client is stuck on a stale shell.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control

# Placeholders substituted into static/js/sw.js when it is served.
#
# The S105 suppressions are for flake8-bandit, which reads any constant whose
# name ends in TOKEN as a credential. These two are literal placeholder strings
# that ship in a source file and are replaced at request time.

#: Replaced with the release version, so a deploy invalidates the shell cache.
CACHE_VERSION_TOKEN = "__CACHE_VERSION__"  # noqa: S105

#: Replaced with whether this is a development server. See sw.js.
DEV_TOKEN = "__DEV__"  # noqa: S105


@cache_control(max_age=0, no_cache=True, must_revalidate=True)
def service_worker(request: HttpRequest) -> HttpResponse:
    """Serve the service worker from the site root, cache version filled in.

    Never cached itself. A stale service worker is the one thing a browser
    cannot recover from on its own — it would keep serving an old shell and
    never fetch the new worker that would fix it.
    """
    source = Path(settings.BASE_DIR) / "static" / "js" / "sw.js"
    body = (
        source.read_text(encoding="utf-8")
        .replace(CACHE_VERSION_TOKEN, settings.RELEASE_VERSION)
        # Under DEBUG the worker stands down rather than serving a stale
        # module out of a cache whose version never changes. See sw.js.
        .replace(DEV_TOKEN, "true" if settings.DEBUG else "false")
    )
    return HttpResponse(body, content_type="text/javascript")


def offline(request: HttpRequest) -> HttpResponse:
    """Render the page shown when a navigation fails and nothing is cached.

    Precached at install, so it is available precisely when nothing else is.
    """
    return render(request, "offline.html", status=200)
