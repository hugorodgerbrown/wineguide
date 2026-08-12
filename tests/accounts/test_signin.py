"""
Tests for passwordless sign-in.

The interesting cases are the ones where a link should stop working: after it
has been used, after it has expired, and after someone has edited it.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tokens import SALT, make_token, read_token, token_matches
from tests.factories import make_user

pytestmark = pytest.mark.django_db

SIGN_IN = reverse("accounts:sign_in")


@pytest.fixture(autouse=True)
def _clear_throttle() -> None:
    """The sign-in throttle is a cache key, and LocMemCache outlives a test."""
    cache.clear()


class TestTokens:
    def test_a_fresh_token_verifies(self) -> None:
        user = make_user()
        payload = read_token(make_token(user))
        assert payload is not None
        assert token_matches(user, payload)

    def test_a_tampered_token_does_not(self) -> None:
        token = make_token(make_user())
        assert read_token(token[:-3] + "aaa") is None

    def test_an_expired_token_does_not(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patching the max age is the same test as waiting fifteen minutes,
        and does not need a clock-freezing dependency for one case.
        """
        token = make_token(make_user())
        monkeypatch.setattr("apps.accounts.tokens.MAX_AGE_SECONDS", -1)
        assert read_token(token) is None

    def test_a_used_token_stops_matching(self) -> None:
        """`last_login` is signed into the payload, so signing in invalidates
        every outstanding link without anything being stored.
        """
        user = make_user()
        payload = read_token(make_token(user))
        assert payload is not None

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        assert token_matches(user, payload) is False

    def test_a_payload_without_a_pk_is_rejected(self) -> None:
        assert read_token(signing.dumps({"nope": 1}, salt=SALT)) is None


class TestSignInForm:
    def test_renders(self, client: Client) -> None:
        assert client.get(SIGN_IN).status_code == 200

    def test_sends_a_link_to_a_known_address(self, client: Client) -> None:
        make_user("taster@example.com")
        response = client.post(SIGN_IN, {"email": "taster@example.com"})
        assert response.status_code == 200
        assert len(mail.outbox) == 1
        assert "/accounts/sign-in/" in mail.outbox[0].body

    def test_creates_an_account_for_an_unknown_address(self, client: Client) -> None:
        """There is nothing to an account beyond a journal, so sign-up and
        sign-in are the same act.
        """
        client.post(SIGN_IN, {"email": "new@example.com"})
        assert get_user_model().objects.filter(email="new@example.com").exists()

    def test_says_the_same_thing_either_way(self, client: Client) -> None:
        """Otherwise the form is an oracle for who has registered.

        Compared by status and template rather than by bytes: the page echoes
        the address back, so two responses for two addresses can never be
        byte-identical, and asserting that they are would only ever be a test
        of the echo.
        """
        make_user("known@example.com")
        known = client.post(SIGN_IN, {"email": "known@example.com"})
        cache.clear()
        unknown = client.post(SIGN_IN, {"email": "stranger@example.com"})

        assert known.status_code == unknown.status_code == 200
        assert [t.name for t in known.templates] == [t.name for t in unknown.templates]

    def test_rejects_something_that_is_not_an_address(self, client: Client) -> None:
        response = client.post(SIGN_IN, {"email": "not-an-email"})
        assert response.status_code == 400
        assert mail.outbox == []

    def test_throttles_a_second_request_for_the_same_address(
        self, client: Client
    ) -> None:
        """A form that emails anyone who submits it is a way to annoy people."""
        make_user("taster@example.com")
        client.post(SIGN_IN, {"email": "taster@example.com"})
        client.post(SIGN_IN, {"email": "taster@example.com"})
        assert len(mail.outbox) == 1

    def test_a_signed_in_taster_is_sent_to_the_session(self, client: Client) -> None:
        client.force_login(make_user())
        response = client.get(SIGN_IN)
        assert response.status_code == 302
        assert response["Location"] == reverse("tastings:start")


class TestVerify:
    def test_signs_the_taster_in(self, client: Client) -> None:
        user = make_user()
        url = reverse("accounts:verify", kwargs={"token": make_token(user)})

        response = client.get(url)

        assert response.status_code == 302
        assert client.session.get("_auth_user_id") == str(user.pk)

    def test_a_link_works_only_once(self, client: Client) -> None:
        user = make_user()
        url = reverse("accounts:verify", kwargs={"token": make_token(user)})
        client.get(url)
        client.logout()

        assert client.get(url).status_code == 400

    def test_a_nonsense_token_is_refused(self, client: Client) -> None:
        url = reverse("accounts:verify", kwargs={"token": "nonsense"})
        assert client.get(url).status_code == 400

    def test_a_token_for_a_deleted_account_is_refused(self, client: Client) -> None:
        user = make_user()
        token = make_token(user)
        user.delete()
        url = reverse("accounts:verify", kwargs={"token": token})
        assert client.get(url).status_code == 400


class TestSignOut:
    def test_signs_out_on_post(self, client: Client) -> None:
        client.force_login(make_user())
        response = client.post(reverse("accounts:sign_out"))
        assert response.status_code == 302
        assert "_auth_user_id" not in client.session

    def test_refuses_get(self, client: Client) -> None:
        """A GET sign-out can be fired by any image tag on any page, and being
        logged out mid-tasting is the interruption PRD §7 forbids.
        """
        client.force_login(make_user())
        assert client.get(reverse("accounts:sign_out")).status_code == 405
        assert "_auth_user_id" in client.session
