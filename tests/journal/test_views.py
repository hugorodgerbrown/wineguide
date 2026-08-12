"""
Tests for the journal.

Two things carry most of the weight here: that one taster can never see
another's notes, and that the filters are forgiving — a journal search is
someone half-remembering a wine, not composing a query.
"""

from __future__ import annotations

import pytest
from django.http import QueryDict
from django.test import Client
from django.urls import reverse

from apps.core.enums import Phase, SessionStatus, WineType
from apps.journal.filters import apply_filters, parse_filters, visible_sessions
from apps.lexicon.models import Lexicon
from apps.tastings.models import TastingSession
from tests.factories import (
    make_lexicon,
    make_option,
    make_question,
    make_response,
    make_session,
    make_user,
)

pytestmark = pytest.mark.django_db

LIST = reverse("journal:list")


def query(**params: str) -> QueryDict:
    """Build a QueryDict the way request.GET arrives."""
    q = QueryDict(mutable=True)
    q.update(params)
    return q


@pytest.fixture
def lexicon() -> Lexicon:
    lexicon = make_lexicon("2026.1")
    colour = make_question(lexicon, "colour", phase=Phase.LOOK)
    make_option(colour, "ruby", swatch="#8e1220")
    quality = make_question(lexicon, "quality", phase=Phase.CONCLUDE)
    make_option(quality, "good", label="Good", order=0)
    make_option(quality, "outstanding", label="Outstanding", order=1)
    return lexicon


class TestParseFilters:
    def test_reads_a_search_term(self) -> None:
        assert parse_filters(query(q=" barolo ")).q == "barolo"

    def test_drops_a_wine_type_that_is_not_a_style(self) -> None:
        filters = parse_filters(query(wine_type="mead"))
        assert filters.wine_type == ""
        assert "wine_type" in filters.ignored

    def test_drops_a_date_it_cannot_read(self) -> None:
        """Better than an error page for someone typing into a date box."""
        filters = parse_filters(query(date_from="last tuesday"))
        assert filters.date_from is None
        assert "date_from" in filters.ignored

    def test_reads_a_valid_date(self) -> None:
        assert parse_filters(query(date_from="2026-03-04")).date_from is not None

    def test_any_applied_is_false_with_nothing_set(self) -> None:
        assert parse_filters(query()).any_applied is False

    def test_any_applied_is_true_with_a_term(self) -> None:
        assert parse_filters(query(q="barolo")).any_applied is True


class TestApplyFilters:
    def test_matches_a_producer(self, lexicon: Lexicon) -> None:
        user = make_user()
        wanted = make_session(user, lexicon, producer="Paolo Scavino")
        make_session(user, lexicon, producer="Domaine Leflaive")

        found = apply_filters(visible_sessions(user), parse_filters(query(q="scavino")))

        assert list(found) == [wanted]

    def test_matches_the_revealed_grape(self, lexicon: Lexicon) -> None:
        user = make_user()
        wanted = make_session(user, lexicon, actual_grape="Nebbiolo")
        make_session(user, lexicon, actual_grape="Merlot")

        found = apply_filters(visible_sessions(user), parse_filters(query(q="nebb")))

        assert list(found) == [wanted]

    def test_grape_matches_either_side_of_the_guess(self, lexicon: Lexicon) -> None:
        """Both "everything I thought was Nebbiolo" and "everything that
        actually was" are plausible searches.
        """
        user = make_user()
        guessed = make_session(user, lexicon, guessed_grape="nebbiolo")
        actual = make_session(user, lexicon, actual_grape="Nebbiolo")

        found = apply_filters(
            visible_sessions(user), parse_filters(query(grape="nebbiolo"))
        )

        assert set(found) == {guessed, actual}

    def test_filters_by_style(self, lexicon: Lexicon) -> None:
        user = make_user()
        red = make_session(user, lexicon, wine_type=WineType.STILL_RED)
        make_session(user, lexicon, wine_type=WineType.STILL_WHITE)

        found = apply_filters(
            visible_sessions(user), parse_filters(query(wine_type="still_red"))
        )

        assert list(found) == [red]

    def test_filters_by_quality(self, lexicon: Lexicon) -> None:
        user = make_user()
        good = make_session(user, lexicon, quality="outstanding")
        make_session(user, lexicon, quality="good")

        found = apply_filters(
            visible_sessions(user), parse_filters(query(quality="outstanding"))
        )

        assert list(found) == [good]


class TestVisibleSessions:
    def test_scopes_to_one_taster(self, lexicon: Lexicon) -> None:
        mine = make_session(make_user("me@example.com"), lexicon)
        make_session(make_user("them@example.com"), lexicon)
        assert list(visible_sessions(mine.user)) == [mine]


class TestJournalList:
    def test_requires_sign_in(self, client: Client) -> None:
        assert client.get(LIST).status_code == 302

    def test_lists_the_taster_s_own_sessions(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        user = make_user()
        client.force_login(user)
        make_session(user, lexicon, producer="Scavino")

        assert "Scavino" in client.get(LIST).content.decode()

    def test_does_not_list_anyone_else_s(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        client.force_login(make_user("me@example.com"))
        make_session(make_user("them@example.com"), lexicon, producer="Secret")

        assert "Secret" not in client.get(LIST).content.decode()

    def test_htmx_gets_only_the_results(self, client: Client, lexicon: Lexicon) -> None:
        user = make_user()
        client.force_login(user)
        make_session(user, lexicon)

        response = client.get(LIST, headers={"hx-request": "true"})

        assert [t.name for t in response.templates] == ["journal/_results.html"]

    def test_a_plain_request_gets_the_whole_page(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        client.force_login(make_user())
        response = client.get(LIST)
        assert "journal/list.html" in [t.name for t in response.templates]

    def test_says_so_when_nothing_has_been_tasted(self, client: Client) -> None:
        client.force_login(make_user())
        assert "No tastings yet" in client.get(LIST).content.decode()


class TestDetail:
    def test_renders_the_answers_with_their_labels(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon, status=SessionStatus.COMPLETED)
        make_response(session, "quality", ["outstanding"], phase=Phase.CONCLUDE)

        content = client.get(session.get_absolute_url()).content.decode()

        assert "Outstanding" in content

    def test_shows_a_skipped_question_as_skipped(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)
        make_response(session, "colour", [], phase=Phase.LOOK, skipped=True)

        assert "Skipped" in client.get(session.get_absolute_url()).content.decode()

    def test_renders_an_answer_whose_option_has_since_gone(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        """A note that silently loses a line is worse than one with an ugly
        line, so an unresolvable code falls back to itself.
        """
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)
        make_response(session, "colour", ["mauve"], phase=Phase.LOOK)

        assert "mauve" in client.get(session.get_absolute_url()).content.decode()

    def test_another_taster_gets_a_404(self, client: Client, lexicon: Lexicon) -> None:
        client.force_login(make_user("me@example.com"))
        theirs = make_session(make_user("them@example.com"), lexicon)

        assert client.get(theirs.get_absolute_url()).status_code == 404


class TestEdit:
    def test_saves_the_wine_details(self, client: Client, lexicon: Lexicon) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)
        url = reverse("journal:edit", kwargs={"uuid": session.uuid})

        client.post(
            url,
            {
                "wine_name": "Barolo",
                "producer": "Scavino",
                "region": "Piedmont",
                "vintage": "2018",
                "actual_grape": "Nebbiolo",
                "actual_origin": "Italy",
            },
        )

        session.refresh_from_db()
        assert session.wine_name == "Barolo"
        assert session.vintage == 2018
        assert session.actual_grape == "Nebbiolo"

    def test_drops_a_vintage_that_is_not_a_number(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        """Someone correcting a producer's spelling should not be stopped by
        what they typed in another box.
        """
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)

        client.post(
            reverse("journal:edit", kwargs={"uuid": session.uuid}),
            {"producer": "Scavino", "vintage": "nineteen eighty"},
        )

        session.refresh_from_db()
        assert session.producer == "Scavino"
        assert session.vintage is None

    def test_another_taster_cannot_edit(self, client: Client, lexicon: Lexicon) -> None:
        client.force_login(make_user("me@example.com"))
        theirs = make_session(make_user("them@example.com"), lexicon)
        url = reverse("journal:edit", kwargs={"uuid": theirs.uuid})

        assert client.post(url, {"producer": "Hacked"}).status_code == 404


class TestDelete:
    def test_deletes_on_post(self, client: Client, lexicon: Lexicon) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)

        response = client.post(reverse("journal:delete", kwargs={"uuid": session.uuid}))

        assert response.status_code == 302
        assert not TastingSession.objects.filter(pk=session.pk).exists()

    def test_refuses_get(self, client: Client, lexicon: Lexicon) -> None:
        user = make_user()
        client.force_login(user)
        session = make_session(user, lexicon)

        assert (
            client.get(
                reverse("journal:delete", kwargs={"uuid": session.uuid})
            ).status_code
            == 405
        )
        assert TastingSession.objects.filter(pk=session.pk).exists()

    def test_another_taster_cannot_delete(
        self, client: Client, lexicon: Lexicon
    ) -> None:
        client.force_login(make_user("me@example.com"))
        theirs = make_session(make_user("them@example.com"), lexicon)

        response = client.post(reverse("journal:delete", kwargs={"uuid": theirs.uuid}))

        assert response.status_code == 404
        assert TastingSession.objects.filter(pk=theirs.pk).exists()
