"""
Tests for the client payload.

The payload is the whole contract between the server and the client state
machine — the client never asks a follow-up question — so these assert its
shape as carefully as its contents.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.core.enums import Axis, Control, Phase, WineType
from apps.lexicon.models import Lexicon
from apps.lexicon.payload import build_payload
from tests.factories import make_lexicon, make_option, make_question

pytestmark = pytest.mark.django_db


@pytest.fixture
def lexicon() -> Lexicon:
    """A small lexicon covering every shape the payload can carry."""
    lexicon = make_lexicon("2026.1")

    clarity = make_question(lexicon, "clarity", phase=Phase.LOOK, order=0)
    make_option(clarity, "clear", order=0)
    make_option(clarity, "hazy", order=1)

    colour = make_question(lexicon, "colour", phase=Phase.LOOK, order=1)
    make_option(colour, "ruby", swatch="#8e1220", wine_types=[WineType.STILL_RED])
    make_option(colour, "lemon", swatch="#f2e08c", wine_types=[WineType.STILL_WHITE])

    tannin = make_question(
        lexicon,
        "tannin",
        phase=Phase.TASTE,
        control=Control.SCALE,
        axis=Axis.GRAIN,
        wine_types=[WineType.STILL_RED],
        order=2,
    )
    make_option(tannin, "low")

    aromas = make_question(
        lexicon, "primary_aromas", phase=Phase.SMELL, control=Control.MULTI, order=3
    )
    citrus = make_option(aromas, "citrus", label="Citrus fruit")
    make_option(aromas, "lemon", label="Lemon", parent=citrus)
    make_option(aromas, "lime", label="Lime", parent=citrus)

    return lexicon


class TestBuildPayload:
    def test_carries_the_version_and_style(self, lexicon: Lexicon) -> None:
        payload = build_payload(lexicon, WineType.STILL_RED)
        assert payload["version"] == "2026.1"
        assert payload["wine_type"] == WineType.STILL_RED

    def test_phases_come_in_running_order(self, lexicon: Lexicon) -> None:
        payload = build_payload(lexicon, WineType.STILL_RED)
        assert [p["code"] for p in payload["phases"]] == ["look", "smell", "taste"]

    def test_each_phase_carries_its_label_and_time_budget(
        self, lexicon: Lexicon
    ) -> None:
        look = build_payload(lexicon, WineType.STILL_RED)["phases"][0]
        assert look["label"] == "Look"
        assert look["seconds"] == 45

    def test_a_phase_with_no_applicable_questions_is_dropped(
        self, lexicon: Lexicon
    ) -> None:
        """Not sent empty — the progress indicator must not count a phase the
        taster will never be shown.
        """
        codes = [p["code"] for p in build_payload(lexicon, WineType.ROSE)["phases"]]
        assert "taste" not in codes

    def test_questions_are_filtered_by_wine_type(self, lexicon: Lexicon) -> None:
        white = build_payload(lexicon, WineType.STILL_WHITE)
        assert all(
            q["code"] != "tannin" for p in white["phases"] for q in p["questions"]
        )

    def test_options_are_filtered_by_wine_type(self, lexicon: Lexicon) -> None:
        red = build_payload(lexicon, WineType.STILL_RED)
        colour = next(
            q for p in red["phases"] for q in p["questions"] if q["code"] == "colour"
        )
        assert [o["code"] for o in colour["options"]] == ["ruby"]

    def test_carries_the_control_type(self, lexicon: Lexicon) -> None:
        red = build_payload(lexicon, WineType.STILL_RED)
        controls = {
            q["code"]: q["control"] for p in red["phases"] for q in p["questions"]
        }
        assert controls["tannin"] == "scale"
        assert controls["clarity"] == "single"

    def test_carries_the_axis(self, lexicon: Lexicon) -> None:
        """The axis decides the mark, so it has to reach the client — which
        never asks a follow-up question.
        """
        red = build_payload(lexicon, WineType.STILL_RED)
        axes = {q["code"]: q["axis"] for p in red["phases"] for q in p["questions"]}
        assert axes["tannin"] == "grain"

    def test_an_unmarked_question_carries_an_empty_axis(self, lexicon: Lexicon) -> None:
        """Present and empty, not absent. A missing key would make "no mark"
        indistinguishable from an older payload that predates the field.
        """
        red = build_payload(lexicon, WineType.STILL_RED)
        clarity = next(
            q for p in red["phases"] for q in p["questions"] if q["code"] == "clarity"
        )
        assert clarity["axis"] == ""

    def test_carries_swatches(self, lexicon: Lexicon) -> None:
        red = build_payload(lexicon, WineType.STILL_RED)
        colour = next(
            q for p in red["phases"] for q in p["questions"] if q["code"] == "colour"
        )
        assert colour["options"][0]["swatch"] == "#8e1220"

    def test_nests_descriptors_under_their_category(self, lexicon: Lexicon) -> None:
        red = build_payload(lexicon, WineType.STILL_RED)
        aromas = next(
            q
            for p in red["phases"]
            for q in p["questions"]
            if q["code"] == "primary_aromas"
        )
        assert [o["code"] for o in aromas["options"]] == ["citrus"]
        assert [c["code"] for c in aromas["options"][0]["children"]] == [
            "lemon",
            "lime",
        ]

    def test_is_json_serialisable(self, lexicon: Lexicon) -> None:
        """It goes over the wire and into IndexedDB; nothing exotic may leak
        in from the enums.
        """
        payload = build_payload(lexicon, WineType.STILL_RED)
        assert json.loads(json.dumps(payload)) == payload

    def test_builds_in_a_constant_number_of_queries(
        self, lexicon: Lexicon, django_assert_num_queries: Any
    ) -> None:
        """Three queries whatever the size — the questions, their options
        prefetched, and the inferences. A payload that scaled with the
        vocabulary would be a problem at the one moment the taster is waiting.
        """
        with django_assert_num_queries(3):
            build_payload(lexicon, WineType.STILL_RED)


class TestSeededLexicon:
    """The real vocabulary, as seeded, is what the app actually serves."""

    @pytest.fixture(autouse=True)
    def _seed(self) -> None:
        from django.core.management import call_command

        call_command("seed_lexicon", "2026.1", verbosity=0)

    @pytest.mark.parametrize("wine_type", WineType.values)
    def test_every_style_gets_all_four_phases(self, wine_type: str) -> None:
        from apps.lexicon.models import Lexicon

        payload = build_payload(Lexicon.objects.active(), wine_type)
        assert [p["code"] for p in payload["phases"]] == [
            "look",
            "smell",
            "taste",
            "conclude",
        ]

    @pytest.mark.parametrize("wine_type", WineType.values)
    def test_every_question_offers_at_least_one_option(self, wine_type: str) -> None:
        """A question whose every option was filtered out by style would be a
        dead end the taster cannot answer or skip past cleanly.
        """
        from apps.lexicon.models import Lexicon

        payload = build_payload(Lexicon.objects.active(), wine_type)
        empty = [
            q["code"]
            for p in payload["phases"]
            for q in p["questions"]
            if not q["options"]
        ]
        assert empty == []

    def test_tannin_is_asked_of_reds_and_not_of_whites(self) -> None:
        from apps.lexicon.models import Lexicon

        lexicon = Lexicon.objects.active()

        def codes(wine_type: str) -> set[str]:
            payload = build_payload(lexicon, wine_type)
            return {q["code"] for p in payload["phases"] for q in p["questions"]}

        assert "tannin" in codes(WineType.STILL_RED)
        assert "tannin" not in codes(WineType.STILL_WHITE)

    def test_the_mousse_question_is_asked_only_of_sparkling(self) -> None:
        from apps.lexicon.models import Lexicon

        lexicon = Lexicon.objects.active()

        def codes(wine_type: str) -> set[str]:
            payload = build_payload(lexicon, wine_type)
            return {q["code"] for p in payload["phases"] for q in p["questions"]}

        assert "mousse" in codes(WineType.SPARKLING)
        assert "mousse" not in codes(WineType.STILL_RED)

    def test_a_red_is_not_offered_a_white_grape(self) -> None:
        from apps.lexicon.models import Lexicon

        payload = build_payload(Lexicon.objects.active(), WineType.STILL_RED)
        grapes = next(
            q
            for p in payload["phases"]
            for q in p["questions"]
            if q["code"] == "guess_grape"
        )
        codes = {o["code"] for o in grapes["options"]}
        assert "cabernet_sauvignon" in codes
        assert "riesling" not in codes
