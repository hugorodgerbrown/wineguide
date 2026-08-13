"""
Tests for the session API.

The sync endpoint is the seam where an offline client meets the server, so
most of these are about the awkward cases: a stale write racing a fresh one,
a replay from a queue that does not know what it already sent, someone else's
uuid.
"""

from __future__ import annotations

import json
import uuid as uuid_lib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.core.enums import Phase, SessionStatus, WineType
from apps.lexicon.models import Lexicon
from apps.tastings.models import TastingSession
from tests.factories import make_lexicon, make_question, make_session, make_user

if TYPE_CHECKING:
    # The test client returns its own HttpResponse subclass, which carries
    # `.json()` and a few other conveniences. django-stubs names it, but only
    # in the stubs — it does not exist at runtime, so the import is guarded and
    # `from __future__ import annotations` keeps the annotations as strings.
    from django.test.client import _MonkeyPatchedWSGIResponse as TestResponse

pytestmark = pytest.mark.django_db

SYNC = reverse("tastings_api:sync")
START = datetime(2026, 3, 4, 19, 30, tzinfo=UTC)


@pytest.fixture
def lexicon() -> Lexicon:
    lexicon = make_lexicon("2026.1")
    make_question(lexicon, "clarity", phase=Phase.LOOK)
    make_question(lexicon, "acidity", phase=Phase.TASTE)
    return lexicon


@pytest.fixture
def user() -> User:
    return make_user("taster@example.com")


@pytest.fixture
def auth(client: Client, user: User) -> Client:
    client.force_login(user)
    return client


def body(**overrides: Any) -> dict[str, Any]:
    """A valid sync body, with overrides applied."""
    payload: dict[str, Any] = {
        "uuid": str(uuid_lib.uuid4()),
        "wine_type": WineType.STILL_RED,
        "lexicon_version": "2026.1",
        "status": SessionStatus.IN_PROGRESS,
        "started_at": START.isoformat(),
        "client_updated_at": START.isoformat(),
        "wine": {"name": "Barolo", "producer": "Scavino", "blind": True},
        "actual": {},
        "responses": [
            {"phase": "look", "question": "clarity", "values": ["clear"]},
        ],
    }
    payload.update(overrides)
    return payload


def post(client: Client, payload: dict[str, Any]) -> TestResponse:
    """POST a sync body."""
    return client.post(SYNC, data=json.dumps(payload), content_type="application/json")


def body_of(response: TestResponse) -> dict[str, Any]:
    """Decode a JSON response.

    Django's test client puts `.json()` on its own response subclass, which is
    private in django-stubs. Reading the content is the same thing and needs
    no private import.
    """
    decoded: dict[str, Any] = json.loads(response.content)
    return decoded


class TestLexiconEndpoint:
    def test_requires_sign_in_and_says_so_in_json(self, client: Client) -> None:
        """A redirect to an HTML login page would reach the client as a parse
        error several layers from the actual problem.
        """
        response = client.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"})
        )
        assert response.status_code == 401
        assert body_of(response)["error"]

    def test_returns_the_payload(self, auth: Client, lexicon: Lexicon) -> None:
        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"})
        )
        assert response.status_code == 200
        assert body_of(response)["version"] == "2026.1"

    def test_rejects_an_unknown_style(self, auth: Client, lexicon: Lexicon) -> None:
        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "mead"})
        )
        assert response.status_code == 404

    def test_reports_a_deployment_with_no_active_lexicon(self, auth: Client) -> None:
        """An empty payload would render as a session with no questions —
        say what is wrong instead.
        """
        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"})
        )
        assert response.status_code == 503

    def test_pins_to_a_version_when_asked(self, auth: Client, lexicon: Lexicon) -> None:
        """Reopening a note needs the questions it was actually asked, not
        whatever is current — so the version is a parameter, and the inactive
        one is served on request.
        """
        make_lexicon("2026.2")

        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"}),
            {"version": "2026.1"},
        )

        assert response.status_code == 200
        assert body_of(response)["version"] == "2026.1"

    def test_serves_the_active_version_by_default(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        make_lexicon("2026.2")

        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"})
        )

        assert body_of(response)["version"] == "2026.2"

    def test_says_so_when_the_pinned_version_is_gone(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        """A note can outlive the vocabulary it was taken against. Better a
        clear failure than the wrong questions.
        """
        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"}),
            {"version": "1999.1"},
        )

        assert response.status_code == 503
        assert "1999.1" in body_of(response)["error"]

    def test_is_not_publicly_cacheable(self, auth: Client, lexicon: Lexicon) -> None:
        response = auth.get(
            reverse("tastings_api:lexicon", kwargs={"wine_type": "still_red"})
        )
        assert "private" in response["Cache-Control"]


class TestSyncCreate:
    def test_requires_sign_in(self, client: Client, lexicon: Lexicon) -> None:
        assert post(client, body()).status_code == 401

    def test_creates_a_session(
        self, auth: Client, lexicon: Lexicon, user: User
    ) -> None:
        payload = body()
        response = post(auth, payload)

        assert response.status_code == 200
        assert body_of(response)["applied"] is True
        session = TastingSession.objects.get(uuid=payload["uuid"])
        assert session.user == user
        assert session.producer == "Scavino"
        assert session.tasted_blind is True

    def test_stores_the_responses(self, auth: Client, lexicon: Lexicon) -> None:
        payload = body()
        post(auth, payload)
        session = TastingSession.objects.get(uuid=payload["uuid"])
        assert session.answers() == {"clarity": ["clear"]}

    def test_records_completion_time_when_completed(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        payload = body(status=SessionStatus.COMPLETED)
        post(auth, payload)
        assert TastingSession.objects.get(uuid=payload["uuid"]).completed_at is not None

    def test_refreshes_the_journal_filter_columns(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        make_question(lexicon, "quality", phase=Phase.CONCLUDE)
        payload = body(
            responses=[
                {"phase": "conclude", "question": "quality", "values": ["very_good"]}
            ]
        )
        post(auth, payload)
        assert TastingSession.objects.get(uuid=payload["uuid"]).quality == "very_good"

    def test_returns_the_journal_url(self, auth: Client, lexicon: Lexicon) -> None:
        payload = body()
        assert payload["uuid"] in body_of(post(auth, payload))["url"]


class TestSyncIdempotency:
    def test_replaying_the_same_body_changes_nothing(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        """The offline queue retries blindly; it must be able to."""
        payload = body()
        post(auth, payload)
        second = post(auth, payload)

        assert second.status_code == 200
        assert body_of(second)["applied"] is False
        assert TastingSession.objects.count() == 1

    def test_a_newer_write_replaces_the_responses_wholesale(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        """A merge would resurrect an answer the taster removed."""
        payload = body()
        post(auth, payload)

        later = body(
            uuid=payload["uuid"],
            client_updated_at=(START + timedelta(minutes=5)).isoformat(),
            responses=[
                {"phase": "taste", "question": "acidity", "values": ["high"]},
            ],
        )
        post(auth, later)

        session = TastingSession.objects.get(uuid=payload["uuid"])
        assert session.answers() == {"acidity": ["high"]}

    def test_a_stale_write_is_acknowledged_and_discarded(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        """A second tab saving an old copy must not undo the live one — and
        must not see an error it has no way to act on.
        """
        payload = body(client_updated_at=(START + timedelta(minutes=5)).isoformat())
        post(auth, payload)

        stale = body(
            uuid=payload["uuid"],
            client_updated_at=START.isoformat(),
            responses=[{"phase": "look", "question": "clarity", "values": ["hazy"]}],
        )
        response = post(auth, stale)

        assert response.status_code == 200
        assert body_of(response)["applied"] is False
        assert TastingSession.objects.get(uuid=payload["uuid"]).answers() == {
            "clarity": ["clear"]
        }


class TestSyncOwnership:
    def test_another_taster_gets_a_404_not_a_403(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        """Confirming that a uuid exists tells a stranger something about
        someone else's journal.
        """
        theirs = make_session(user=make_user("them@example.com"), lexicon=lexicon)
        response = post(auth, body(uuid=str(theirs.uuid)))
        assert response.status_code == 404


class TestSyncValidation:
    def test_rejects_a_body_that_is_not_json(self, auth: Client) -> None:
        response = auth.post(SYNC, data="not json", content_type="application/json")
        assert response.status_code == 400

    def test_rejects_a_json_array(self, auth: Client) -> None:
        response = auth.post(SYNC, data="[]", content_type="application/json")
        assert response.status_code == 400

    @pytest.mark.parametrize(
        "field",
        ["uuid", "wine_type", "lexicon_version", "started_at", "client_updated_at"],
    )
    def test_requires_each_field(
        self, auth: Client, lexicon: Lexicon, field: str
    ) -> None:
        payload = body()
        del payload[field]
        response = post(auth, payload)
        assert response.status_code == 400
        assert body_of(response)["field"] == field

    def test_rejects_a_malformed_uuid(self, auth: Client, lexicon: Lexicon) -> None:
        """Passed straight through it would reach the UUIDField lookup and
        raise, which is a 500 for a client mistake.
        """
        response = post(auth, body(uuid="not-a-uuid"))
        assert response.status_code == 400
        assert body_of(response)["field"] == "uuid"

    def test_rejects_an_unknown_wine_type(self, auth: Client, lexicon: Lexicon) -> None:
        assert post(auth, body(wine_type="mead")).status_code == 400

    def test_rejects_an_unknown_status(self, auth: Client, lexicon: Lexicon) -> None:
        assert post(auth, body(status="halfway")).status_code == 400

    def test_rejects_an_unknown_lexicon_version(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        response = post(auth, body(lexicon_version="1999.1"))
        assert response.status_code == 400
        assert body_of(response)["field"] == "lexicon_version"

    def test_rejects_a_naive_timestamp(self, auth: Client, lexicon: Lexicon) -> None:
        """Guessing a zone would put the session hours out and silently lose a
        sync race.
        """
        response = post(auth, body(client_updated_at="2026-03-04T19:30:00"))
        assert response.status_code == 400

    def test_rejects_an_unparseable_timestamp(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        assert post(auth, body(started_at="last tuesday")).status_code == 400

    def test_rejects_responses_that_are_not_a_list(
        self, auth: Client, lexicon: Lexicon
    ) -> None:
        assert post(auth, body(responses={})).status_code == 400

    def test_rejects_an_unknown_phase(self, auth: Client, lexicon: Lexicon) -> None:
        response = post(
            auth, body(responses=[{"phase": "sniff", "question": "x", "values": []}])
        )
        assert response.status_code == 400

    def test_rejects_a_duplicate_question(self, auth: Client, lexicon: Lexicon) -> None:
        """The constraint would catch it, but as an IntegrityError halfway
        through a transaction rather than an answerable message.
        """
        response = post(
            auth,
            body(
                responses=[
                    {"phase": "look", "question": "clarity", "values": ["clear"]},
                    {"phase": "look", "question": "clarity", "values": ["hazy"]},
                ]
            ),
        )
        assert response.status_code == 400
        assert "duplicate" in body_of(response)["error"]

    def test_rejects_non_string_values(self, auth: Client, lexicon: Lexicon) -> None:
        response = post(
            auth, body(responses=[{"phase": "look", "question": "c", "values": [1]}])
        )
        assert response.status_code == 400

    def test_accepts_a_skipped_question(self, auth: Client, lexicon: Lexicon) -> None:
        payload = body(
            responses=[
                {"phase": "look", "question": "clarity", "values": [], "skipped": True}
            ]
        )
        assert post(auth, payload).status_code == 200
        session = TastingSession.objects.get(uuid=payload["uuid"])
        assert session.responses.get().skipped is True

    def test_rejects_get(self, auth: Client) -> None:
        assert auth.get(SYNC).status_code == 405
