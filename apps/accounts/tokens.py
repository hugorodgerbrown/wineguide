"""
apps/accounts/tokens.py — Signed sign-in links.

No passwords: the taster gives an email address and gets a link. That is the
whole of PRD §6.4, which asks for the lightest thing that makes a journal
persist across devices.

The token is a signed, timestamped payload — no database row, so a link cannot
be "used up" by a mail scanner prefetching it and nothing has to be cleaned up.
It is invalidated three ways:

  1. **Age.** `TimestampSigner` carries the issue time; `MAX_AGE_SECONDS`
     bounds it.
  2. **Use.** The payload includes the user's `last_login`, so a successful
     sign-in changes the value the signature was made against and every
     outstanding link for that account stops verifying. This is the same
     trick Django's own password-reset tokens use, and it is what makes the
     link effectively single-use without storing anything.
  3. **Key rotation.** The signature is salted per purpose, so rotating
     `SECRET_KEY` invalidates every outstanding link.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.core import signing

#: Salt, so a signature minted here cannot be replayed against another signer
#: elsewhere in the project.
SALT = "wineguide.accounts.signin"

#: Long enough to survive a slow mail server and a distracted reader; short
#: enough that a link left in an inbox is not a standing key to the account.
MAX_AGE_SECONDS = 15 * 60


def _last_login_stamp(user: AbstractUser) -> str:
    """Return the value that changes when the user signs in.

    A user who has never signed in has `last_login` of None, which is a stable
    value — that is fine, because their first successful sign-in sets it and
    invalidates the link that got them there.
    """
    return user.last_login.isoformat() if user.last_login else ""


def make_token(user: AbstractUser) -> str:
    """Mint a sign-in token for ``user``.

    Args:
        user: The account to sign in.

    Returns:
        A URL-safe signed token.

    """
    return signing.dumps(
        {"pk": user.pk, "stamp": _last_login_stamp(user)},
        salt=SALT,
    )


def read_token(token: str) -> dict[str, object] | None:
    """Verify ``token`` and return its payload.

    Returns None for anything that is not a currently-valid token — expired,
    tampered with, or signed under a different key. The caller cannot tell
    which, and should not: telling a visitor *why* a link failed is telling an
    attacker the same thing.

    Args:
        token: The token from the sign-in link.

    Returns:
        The payload, or None if it does not verify.

    """
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict) or "pk" not in payload:
        return None
    return payload


def token_matches(user: AbstractUser, payload: dict[str, object]) -> bool:
    """Return whether ``payload`` is still valid for ``user``.

    Checks the `last_login` stamp, which is what makes a link stop working
    once it has been used.

    Args:
        user: The account the token names.
        payload: The verified token payload.

    Returns:
        True if the link has not already been spent.

    """
    return payload.get("stamp") == _last_login_stamp(user)
