"""
Tests for the session shell.

The page itself is one script tag and a mount point, so what is worth testing
is the bootstrap: which of the three entry points the taster arrived by, and
what the server hands over when they came to change an answer.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.enums import SessionStatus, WineType
from apps.lexicon.models import Lexicon
from tests.factories import make_lexicon, make_response, make_session, make_user

pytestmark = pytest.mark.django_db


def bootstrap(response) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Pull the embedded bootstrap JSON out of a rendered shell."""
    content = response.content.decode()
    start = content.index('id="session-bootstrap"')
    opening = content.index(">", start) + 1
    data: dict[str, Any] = json.loads(
        content[opening : content.index("</script>", opening)]
    )
    return data


@pytest.fixture
def lexicon() -> Lexicon:
    return make_lexicon("2026.1")


class TestEntryPoints:
    def test_start_may_resume(self, client: Client) -> None:
        client.force_login(make_user())
        assert bootstrap(client.get(reverse("tastings:start")))["resume"] is True

    def test_start_new_may_not(self, client: Client) -> None:
        """Otherwise "new tasting" lands you in a half-finished one, which is
        the app overriding a choice just made.
        """
        client.force_login(make_user())
        assert bootstrap(client.get(reverse("tastings:start_new")))["resume"] is False

    def test_neither_carries_a_session(self, client: Client) -> None:
        client.force_login(make_user())
        for name in ("tastings:start", "tastings:start_new"):
            assert bootstrap(client.get(reverse(name)))["session"] is None

    def test_all_three_require_sign_in(self, client: Client, lexicon: Lexicon) -> None:
        session = make_session(make_user(), lexicon)
        for url in (
            reverse("tastings:start"),
            reverse("tastings:start_new"),
            reverse("tastings:reopen", kwargs={"uuid": session.uuid}),
        ):
            assert client.get(url).status_code == 302


class TestReopen:
    def test_hands_over_the_stored_answers(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon, wine_type=WineType.STILL_WHITE)
        make_response(session, "clarity", values=["clear"])
        make_response(session, "acidity", values=["high"])

        data = bootstrap(
            client.get(reverse("tastings:reopen", kwargs={"uuid": session.uuid}))
        )

        assert data["session"]["answers"] == {
            "clarity": {"values": ["clear"], "skipped": False},
            "acidity": {"values": ["high"], "skipped": False},
        }

    def test_carries_the_identity_the_sync_upserts_on(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        """The same uuid, or reopening a note would create a second one."""
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon, wine_type=WineType.STILL_WHITE)

        data = bootstrap(
            client.get(reverse("tastings:reopen", kwargs={"uuid": session.uuid}))
        )

        assert data["session"]["uuid"] == str(session.uuid)
        assert data["session"]["wineType"] == WineType.STILL_WHITE

    def test_pins_the_lexicon_the_note_was_taken_against(self, client: Client) -> None:
        """A note recorded before a question was added must not come back with
        a gap in it, so the version travels with the session.
        """
        old = make_lexicon("2026.1")
        make_lexicon("2026.2")
        user = make_user()
        client.force_login(user)
        session = make_session(user, old)

        data = bootstrap(
            client.get(reverse("tastings:reopen", kwargs={"uuid": session.uuid}))
        )

        assert data["lexicon_version"] == "2026.1"
        assert data["session"]["lexiconVersion"] == "2026.1"

    def test_never_resumes_something_else(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)

        data = bootstrap(
            client.get(reverse("tastings:reopen", kwargs={"uuid": session.uuid}))
        )

        assert data["resume"] is False

    def test_keeps_a_skip_a_skip(self, client: Client, lexicon: Lexicon) -> None:
        """Skipped and unanswered are different states (PRD §6.1), and a
        round trip through reopening must not collapse them.
        """
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)
        make_response(session, "tannin", values=[], skipped=True)

        data = bootstrap(
            client.get(reverse("tastings:reopen", kwargs={"uuid": session.uuid}))
        )

        assert data["session"]["answers"]["tannin"] == {"values": [], "skipped": True}

    def test_a_completed_note_can_be_reopened(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon, status=SessionStatus.COMPLETED)

        url = reverse("tastings:reopen", kwargs={"uuid": session.uuid})

        assert client.get(url).status_code == 200

    def test_another_taster_cannot_reopen_it(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        client.force_login(make_user("me@example.com"))
        theirs = make_session(make_user("them@example.com"), lexicon)

        url = reverse("tastings:reopen", kwargs={"uuid": theirs.uuid})

        assert client.get(url).status_code == 404
