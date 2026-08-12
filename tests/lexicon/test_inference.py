"""
Tests for the inference layer.

Deliberately parallel to tests/js/test_session_inference.js — the same rule
runs in both places, because the journal is server-rendered and the closing
summary has to work offline. A case added here should be added there.
"""

from __future__ import annotations

import pytest

from apps.core.enums import AromaOrigin, Control, Phase
from apps.lexicon.inference import interpret, selected_codes
from apps.lexicon.models import Inference, Lexicon
from tests.factories import make_lexicon, make_option, make_question

pytestmark = pytest.mark.django_db


@pytest.fixture
def lexicon() -> Lexicon:
    """A lexicon with tagged descriptors on both the nose and the palate."""
    lexicon = make_lexicon("2026.1")

    for code, phase in (("aromas", Phase.SMELL), ("flavours", Phase.TASTE)):
        question = make_question(lexicon, code, phase=phase, control=Control.MULTI)
        baking = make_option(question, "baking", label="Bread and pastry")
        make_option(
            question,
            "brioche",
            label="Brioche",
            parent=baking,
            origin=AromaOrigin.SECONDARY,
            implies="lees",
        )
        dairy = make_option(question, "dairy", label="Dairy")
        make_option(
            question,
            "butter",
            label="Butter",
            parent=dairy,
            origin=AromaOrigin.SECONDARY,
            implies="malolactic",
        )
        make_option(
            question,
            "cream",
            label="Cream",
            parent=dairy,
            origin=AromaOrigin.SECONDARY,
            implies="malolactic",
        )
        citrus = make_option(question, "citrus", label="Citrus")
        make_option(
            question,
            "lemon",
            label="Lemon",
            parent=citrus,
            origin=AromaOrigin.PRIMARY,
        )
        earth = make_option(question, "earth", label="Earth")
        make_option(
            question,
            "mushroom",
            label="Mushroom",
            parent=earth,
            origin=AromaOrigin.TERTIARY,
            implies="bottle_age",
        )

    # An untagged option, of the kind every scale question is made of.
    acidity = make_question(
        lexicon, "acidity", phase=Phase.TASTE, control=Control.SCALE
    )
    make_option(acidity, "high", label="High")

    for order, (code, label) in enumerate(
        [
            ("lees", "Time on the lees"),
            ("malolactic", "Malolactic conversion"),
            ("bottle_age", "Bottle age"),
        ]
    ):
        Inference.objects.create(
            lexicon=lexicon,
            code=code,
            label=label,
            explanation=f"What {label} means.",
            order=order,
        )

    return lexicon


class TestSelectedCodes:
    def test_flattens_every_answer(self) -> None:
        assert selected_codes({"aromas": ["lemon", "butter"], "acidity": ["high"]}) == {
            "lemon",
            "butter",
            "high",
        }

    def test_is_empty_for_an_empty_session(self) -> None:
        assert selected_codes({}) == set()


class TestOriginGroups:
    def test_sorts_descriptors_into_the_framework(self, lexicon: Lexicon) -> None:
        """The taster records what they smell; the app does the filing."""
        groups, _ = interpret(lexicon, {"lemon", "brioche", "mushroom"})

        assert [(g.origin, g.descriptors) for g in groups] == [
            ("primary", ("Lemon",)),
            ("secondary", ("Brioche",)),
            ("tertiary", ("Mushroom",)),
        ]

    def test_groups_come_in_teaching_order(self, lexicon: Lexicon) -> None:
        groups, _ = interpret(lexicon, {"mushroom", "lemon"})
        assert [g.origin for g in groups] == ["primary", "tertiary"]

    def test_omits_an_origin_with_nothing_in_it(self, lexicon: Lexicon) -> None:
        groups, _ = interpret(lexicon, {"lemon"})
        assert [g.origin for g in groups] == ["primary"]

    def test_ignores_untagged_options(self, lexicon: Lexicon) -> None:
        """A scale answer is not a descriptor and must not appear as one."""
        groups, _ = interpret(lexicon, {"high"})
        assert groups == []

    def test_counts_a_descriptor_found_twice_once(self, lexicon: Lexicon) -> None:
        """Aroma and flavour share a vocabulary. Smelling butter and then
        tasting it is one finding, not two.
        """
        groups, _ = interpret(lexicon, {"butter"})
        assert groups[0].descriptors == ("Butter",)


class TestConclusions:
    def test_names_the_process_behind_the_descriptor(self, lexicon: Lexicon) -> None:
        """The point of the whole exercise: the taster is told, not asked."""
        _, conclusions = interpret(lexicon, {"butter"})

        assert [c.code for c in conclusions] == ["malolactic"]
        assert conclusions[0].label == "Malolactic conversion"

    def test_shows_its_working(self, lexicon: Lexicon) -> None:
        """Evidence is the teaching half; the label alone is one more thing to
        memorise.
        """
        _, conclusions = interpret(lexicon, {"butter", "cream"})
        assert conclusions[0].evidence == ("Butter", "Cream")

    def test_fires_on_a_single_descriptor(self, lexicon: Lexicon) -> None:
        """No threshold. One descriptor is enough for a true sentence, and a
        confidence score would imply a precision this does not have.
        """
        _, conclusions = interpret(lexicon, {"brioche"})
        assert [c.code for c in conclusions] == ["lees"]

    def test_draws_several_at_once(self, lexicon: Lexicon) -> None:
        _, conclusions = interpret(lexicon, {"brioche", "butter", "mushroom"})
        assert [c.code for c in conclusions] == ["lees", "malolactic", "bottle_age"]

    def test_comes_in_the_lexicon_s_order(self, lexicon: Lexicon) -> None:
        _, conclusions = interpret(lexicon, {"mushroom", "brioche"})
        assert [c.code for c in conclusions] == ["lees", "bottle_age"]

    def test_draws_nothing_from_untagged_answers(self, lexicon: Lexicon) -> None:
        _, conclusions = interpret(lexicon, {"high"})
        assert conclusions == []

    def test_draws_nothing_from_an_empty_session(self, lexicon: Lexicon) -> None:
        groups, conclusions = interpret(lexicon, set())
        assert (groups, conclusions) == ([], [])

    def test_ignores_an_implication_with_no_inference_defined(
        self, lexicon: Lexicon
    ) -> None:
        """A descriptor tagged with a code nobody wrote an explanation for is
        a data error, and must not render as an empty conclusion.
        """
        question = lexicon.questions.get(code="aromas")
        make_option(
            question,
            "banana",
            label="Banana",
            origin=AromaOrigin.PRIMARY,
            implies="carbonic",
        )

        groups, conclusions = interpret(lexicon, {"banana"})

        assert [g.origin for g in groups] == ["primary"]
        assert conclusions == []


class TestSeededLexicon:
    """The real vocabulary, which is what the app actually serves."""

    @pytest.fixture(autouse=True)
    def _seed(self) -> None:
        from django.core.management import call_command

        call_command("seed_lexicon", "2026.1", verbosity=0)

    def test_bread_means_lees(self) -> None:
        _, conclusions = interpret(Lexicon.objects.active(), {"bread_dough"})
        assert [c.code for c in conclusions] == ["lees"]

    def test_butter_means_malolactic(self) -> None:
        _, conclusions = interpret(Lexicon.objects.active(), {"butter"})
        assert [c.code for c in conclusions] == ["malolactic"]

    def test_vanilla_means_oak(self) -> None:
        _, conclusions = interpret(Lexicon.objects.active(), {"vanilla"})
        assert [c.code for c in conclusions] == ["oak"]

    def test_banana_means_carbonic_maceration(self) -> None:
        _, conclusions = interpret(Lexicon.objects.active(), {"banana"})
        assert [c.code for c in conclusions] == ["carbonic"]

    def test_every_implication_has_an_explanation(self) -> None:
        """A descriptor pointing at an inference nobody wrote is a silent
        hole — the taster picks it and is told nothing.
        """
        lexicon = Lexicon.objects.active()
        implied = set(
            lexicon.questions.filter()
            .values_list("options__implies", flat=True)
            .distinct()
        ) - {"", None}
        defined = set(lexicon.inferences.values_list("code", flat=True))
        assert implied - defined == set()

    def test_the_taster_is_never_asked_about_winemaking(self) -> None:
        """The whole point. If a question like this comes back, the app is
        demanding the deduction instead of doing it.
        """
        codes = set(Lexicon.objects.active().questions.values_list("code", flat=True))
        assert "winemaking" not in codes
