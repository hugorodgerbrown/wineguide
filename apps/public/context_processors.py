"""apps/public/context_processors.py — Template context available site-wide."""

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, str]:
    """Expose site identity and the release version to every template.

    RELEASE_VERSION is appended to static-asset URLs in base.html so a deploy
    busts the browser cache for CSS and JS that keep the same filename.
    """
    return {
        "SITE_NAME": settings.SITE_NAME,
        "RELEASE_VERSION": settings.RELEASE_VERSION,
    }
