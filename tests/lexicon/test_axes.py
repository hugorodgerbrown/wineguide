"""
Tests for the sensory axes the seeded vocabulary assigns.

The axis decides which mark a question's options carry, and a question with
the wrong one — or with none where it needs one — fails silently: the screen
renders, the row is just missing its drawing. These assert the assignment
rather than the rendering, because the assignment is the part that is data.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.core.enums import Axis, Control, Phase
from apps.lexicon.models import Lexicon, Question

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _seed() -> None:
    call_command("seed_lexicon", "2026.1", verbosity=0)


@pytest.fixture
def questions() -> list[Question]:
    return list(Lexicon.objects.active().questions.all())


class TestSeededAxes:
    def test_every_observed_scale_has_an_axis(self, questions: list[Question]) -> None:
        """A scale in Look, Smell or Taste is a sensation, and a sensation has
        a geometry. One without an axis is a rung the taster is asked to judge
        with nothing to show them what it means.
        """
        unmarked = [
            q.code
            for q in questions
            if q.control == Control.SCALE and q.phase != Phase.CONCLUDE and not q.axis
        ]
        assert unmarked == []

    def test_nothing_in_conclude_carries_an_axis(
        self, questions: list[Question]
    ) -> None:
        """Quality and confidence are ordered, but they are judgements the
        taster arrives at rather than sensations they receive, so there is no
        geometry a mark could illustrate.
        """
        marked = [q.code for q in questions if q.phase == Phase.CONCLUDE and q.axis]
        assert marked == []

    def test_every_axis_is_a_real_one(self, questions: list[Question]) -> None:
        """`choices` is not validated on `create`, so a typo in seed_data would
        reach the client and render nothing at all.
        """
        used = {q.axis for q in questions if q.axis}
        assert used <= set(Axis.values)

    @pytest.mark.parametrize(
        ("code", "axis"),
        [
            ("appearance_intensity", Axis.SWATCH),
            ("colour", Axis.SWATCH),
            ("nose_intensity", Axis.CARRY),
            ("sweetness", Axis.FILL),
            ("acidity", Axis.SPREAD),
            ("alcohol", Axis.RISE),
            ("body", Axis.WEIGHT),
            ("flavour_intensity", Axis.BURST),
            ("finish", Axis.LENGTH),
        ],
    )
    def test_each_sensation_takes_its_own_geometry(
        self, questions: list[Question], code: str, axis: str
    ) -> None:
        by_code = {q.code: q for q in questions}
        assert by_code[code].axis == axis

    def test_tannin_and_mousse_share_the_friction_mark(
        self, questions: list[Question]
    ) -> None:
        """The axis, not the question, decides the mark — and both of these are
        things the mouth feels rather than tastes. Mousse also proves the mark
        does not follow the control type: it is a `single`, and it is ordered
        all the same.
        """
        by_code = {q.code: q for q in questions}
        assert by_code["tannin"].axis == Axis.GRAIN
        assert by_code["mousse"].axis == Axis.GRAIN
        assert by_code["mousse"].control == Control.SINGLE

    def test_categorical_questions_take_no_mark(
        self, questions: list[Question]
    ) -> None:
        """No ramp runs through "clear" and "hazy", and none through ninety
        aroma descriptors either.
        """
        by_code = {q.code: q for q in questions}
        assert by_code["clarity"].axis == ""
        assert by_code["condition"].axis == ""
        assert by_code["aromas"].axis == ""
        assert by_code["flavours"].axis == ""
