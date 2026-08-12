"""
apps/accounts/views.py — Passwordless sign-in.

Three views: ask for an email, follow the link in it, sign out.

Two behaviours are deliberate and easy to "fix" into bugs:

  * The sign-in form gives the same confirmation whether or not the address
    has an account. Otherwise the form is an oracle for who has registered.
  * An unknown address creates an account. There is nothing to a wineguide
    account beyond a journal, so sign-up and sign-in are the same act, and
    making the taster pick which one they are doing is asking them to care
    about our data model.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .tokens import make_token, read_token, token_matches

#: One link per address per minute. A sign-in form that emails anyone who
#: submits it is an open relay for annoying people; this is the cheapest
#: thing that stops it being useful for that.
THROTTLE_SECONDS = 60


def _throttled(email: str) -> bool:
    """Return whether ``email`` was sent a link too recently.

    `cache.add` is atomic — it sets the key only if absent and reports
    whether it did — so two simultaneous submissions cannot both pass.
    """
    return not cache.add(f"signin:{email.lower()}", 1, THROTTLE_SECONDS)


def _send_link(request: HttpRequest, user: AbstractUser) -> None:
    """Email ``user`` a sign-in link.

    The URL is built from the request rather than from a configured hostname,
    so the link works on localhost, on a tunnel and in production without a
    setting to keep in step.
    """
    url = request.build_absolute_uri(
        reverse("accounts:verify", kwargs={"token": make_token(user)})
    )
    send_mail(
        subject=_("Your %(site)s sign-in link") % {"site": settings.SITE_NAME},
        message=_(
            "Open this link to sign in. It expires in 15 minutes and works "
            "once.\n\n%(url)s\n\nIf you did not ask for it, ignore this "
            "message — nothing has changed."
        )
        % {"url": url},
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
    )


@require_http_methods(["GET", "POST"])
def sign_in(request: HttpRequest) -> HttpResponse:
    """Ask for an email address and send a sign-in link to it."""
    if request.user.is_authenticated:
        return redirect("tastings:start")

    if request.method == "GET":
        return render(request, "accounts/sign_in.html")

    email = (request.POST.get("email") or "").strip()
    try:
        validate_email(email)
    except ValidationError:
        return render(
            request,
            "accounts/sign_in.html",
            {"error": _("That does not look like an email address."), "email": email},
            status=400,
        )

    if not _throttled(email):
        user_model = get_user_model()
        user, _created = user_model.objects.get_or_create(
            email__iexact=email,
            defaults={"username": email, "email": email},
        )
        _send_link(request, user)

    # Same response either way — sent, or throttled. See the module docstring.
    return render(request, "accounts/sign_in_sent.html", {"email": email})


def verify(request: HttpRequest, token: str) -> HttpResponse:
    """Sign the taster in from a link, if it still verifies."""
    payload = read_token(token)
    user = None
    if payload is not None:
        user = get_user_model().objects.filter(pk=str(payload["pk"])).first()

    if user is None or payload is None or not token_matches(user, payload):
        return render(request, "accounts/link_invalid.html", status=400)

    # `last_login` is what the token was signed against, so setting it is what
    # spends the link. login() does it for us.
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(request.GET.get("next") or "tastings:start")


@require_http_methods(["POST"])
def sign_out(request: HttpRequest) -> HttpResponse:
    """Sign out.

    POST only: a GET sign-out can be triggered by any image tag on any page,
    and being logged out mid-tasting is exactly the interruption PRD §7 says
    the app must not inflict.
    """
    logout(request)
    return redirect("accounts:sign_in")


def _touch_last_login(user: AbstractUser) -> None:
    """Set `last_login` without a full save.

    Used by tests and by any path that needs to spend outstanding links
    without going through `login()`.
    """
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
