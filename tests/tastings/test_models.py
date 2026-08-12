"""Tests for the tasting record."""

from __future__ import annotations

import pytest
from django.db.utils import IntegrityError

from apps.core.enums import Phase, SessionStatus, WineType
from apps.lexicon.models import Lexicon
from tests.factories import (
    make_lexicon,
    make_option,
    make_question,
    make_response,
    make_session,
    make_user,
)

pytestmark = pytest.mark.django_db


class TestTastingSession:
    def test_gets_a_uuid_without_being_given_one(self) -> None:
        """The client normally supplies it, but a session created any other
        way still needs an identity.
        """
        assert make_session().uuid is not None

    def test_uuid_is_unique(self) -> None:
        first = make_session()
        with pytest.raises(IntegrityError):
            make_session(uuid=first.uuid)

    def test_display_name_prefers_producer_and_wine(self) -> None:
        session = make_session(producer="Paolo Scavino", wine_name="Barolo")
        assert session.display_name == "Paolo Scavino Barolo"

    def test_display_name_uses_whichever_half_is_known(self) -> None:
        assert make_session(wine_name="Barolo").display_name == "Barolo"
        assert make_session(producer="Scavino").display_name == "Scavino"

    def test_display_name_falls_back_to_the_style(self) -> None:
        """A blind tasting that was never revealed has no name — an empty row
        in the journal helps nobody.
        """
        session = make_session(wine_type=WineType.STILL_RED, tasted_blind=True)
        assert session.display_name == "Still red"

    def test_is_complete_tracks_status(self) -> None:
        assert make_session().is_complete is False
        assert make_session(status=SessionStatus.COMPLETED).is_complete is True

    def test_for_user_scopes_to_one_taster(self) -> None:
        from apps.tastings.models import TastingSession

        mine = make_session(user=make_user("me@example.com"))
        make_session(user=make_user("them@example.com"))
        assert list(TastingSession.objects.for_user(mine.user)) == [mine]

    def test_completed_scopes_to_finished_sessions(self) -> None:
        from apps.tastings.models import TastingSession

        make_session()
        done = make_session(status=SessionStatus.COMPLETED)
        assert list(TastingSession.objects.completed()) == [done]


class TestAnswers:
    def test_maps_question_codes_to_values(self) -> None:
        session = make_session()
        make_response(session, "clarity", ["clear"])
        make_response(session, "acidity", ["high"], phase=Phase.TASTE)
        assert session.answers() == {"clarity": ["clear"], "acidity": ["high"]}

    def test_omits_skipped_questions(self) -> None:
        """Unsure is a legitimate outcome and should read as absence, not as
        an empty answer.
        """
        session = make_session()
        make_response(session, "clarity", [], skipped=True)
        assert session.answers() == {}

    def test_keeps_every_value_of_a_multi_select(self) -> None:
        session = make_session()
        make_response(session, "primary_aromas", ["lemon", "lime"], phase=Phase.SMELL)
        assert session.answers()["primary_aromas"] == ["lemon", "lime"]


class TestPhaseResponse:
    def test_one_answer_per_question_per_session(self) -> None:
        session = make_session()
        make_response(session, "clarity", ["clear"])
        with pytest.raises(IntegrityError):
            make_response(session, "clarity", ["hazy"])

    def test_the_same_question_may_be_answered_in_another_session(self) -> None:
        user = make_user()
        lexicon = make_lexicon()
        make_response(make_session(user, lexicon), "clarity", ["clear"])
        make_response(make_session(user, lexicon), "clarity", ["hazy"])

    def test_str_reads_as_the_answer(self) -> None:
        session = make_session()
        response = make_response(session, "primary_aromas", ["lemon", "lime"])
        assert str(response) == "primary_aromas: lemon, lime"

    def test_str_says_so_when_skipped(self) -> None:
        session = make_session()
        response = make_response(session, "tannin", [], skipped=True)
        assert str(response) == "tannin: skipped"


class TestSyncDenormalisedFields:
    """The journal's filter columns are a cache of the responses."""

    @pytest.fixture
    def lexicon(self) -> Lexicon:
        lexicon = make_lexicon()
        colour = make_question(lexicon, "colour", phase=Phase.LOOK)
        make_option(colour, "ruby", swatch="#8e1220")
        make_option(colour, "garnet", swatch="#7b2318")
        make_question(lexicon, "quality", phase=Phase.CONCLUDE)
        make_question(lexicon, "guess_grape", phase=Phase.CONCLUDE)
        return lexicon

    def test_copies_quality_and_the_grape_guess(self, lexicon: Lexicon) -> None:
        session = make_session(lexicon=lexicon)
        make_response(session, "quality", ["very_good"], phase=Phase.CONCLUDE)
        make_response(session, "guess_grape", ["nebbiolo"], phase=Phase.CONCLUDE)

        session.sync_denormalised_fields()

        session.refresh_from_db()
        assert session.quality == "very_good"
        assert session.guessed_grape == "nebbiolo"

    def test_resolves_the_colour_to_its_swatch(self, lexicon: Lexicon) -> None:
        session = make_session(lexicon=lexicon)
        make_response(session, "colour", ["garnet"])

        session.sync_denormalised_fields()

        session.refresh_from_db()
        assert session.colour_hex == "#7b2318"

    def test_leaves_the_columns_empty_when_nothing_was_answered(
        self, lexicon: Lexicon
    ) -> None:
        session = make_session(lexicon=lexicon)

        session.sync_denormalised_fields()

        session.refresh_from_db()
        assert (session.quality, session.guessed_grape, session.colour_hex) == (
            "",
            "",
            "",
        )

    def test_clears_a_column_when_the_answer_is_withdrawn(
        self, lexicon: Lexicon
    ) -> None:
        """Sync runs after every upsert, so an answer removed on the client
        must not leave a stale value behind in the journal's filters.
        """
        session = make_session(lexicon=lexicon, quality="outstanding")
        session.sync_denormalised_fields()
        session.refresh_from_db()
        assert session.quality == ""

    def test_ignores_a_colour_from_a_different_lexicon(self, lexicon: Lexicon) -> None:
        """Codes are only unique within a version; resolving one against the
        wrong version would show the wrong swatch.
        """
        other = make_lexicon("other", active=False)
        colour = make_question(other, "colour", phase=Phase.LOOK)
        make_option(colour, "mauve", swatch="#ff00ff")

        session = make_session(lexicon=lexicon)
        make_response(session, "colour", ["mauve"])
        session.sync_denormalised_fields()

        session.refresh_from_db()
        assert session.colour_hex == ""
