"""Tests for the lexicon models."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from apps.core.enums import Phase, WineType
from apps.lexicon.models import Lexicon, applies_to
from tests.factories import make_lexicon, make_option, make_question

pytestmark = pytest.mark.django_db


class TestAppliesTo:
    def test_an_empty_list_means_every_style(self) -> None:
        assert applies_to([], WineType.STILL_RED) is True
        assert applies_to([], WineType.SPARKLING) is True

    def test_a_named_style_matches(self) -> None:
        assert applies_to([WineType.STILL_RED], WineType.STILL_RED) is True

    def test_an_unnamed_style_does_not(self) -> None:
        assert applies_to([WineType.STILL_RED], WineType.STILL_WHITE) is False


class TestLexicon:
    def test_active_returns_the_active_one(self) -> None:
        make_lexicon("old", active=False)
        current = make_lexicon("new")
        assert Lexicon.objects.active() == current

    def test_active_raises_when_none_is_active(self) -> None:
        make_lexicon("only", active=False)
        with pytest.raises(Lexicon.DoesNotExist):
            Lexicon.objects.active()

    def test_the_database_refuses_a_second_active_version(self) -> None:
        """The constraint, not application code, is what holds this."""
        make_lexicon("first")
        with pytest.raises(IntegrityError):
            Lexicon.objects.create(version="second", is_active=True)

    def test_str_marks_the_active_version(self) -> None:
        assert str(make_lexicon("2026.1")) == "2026.1 (active)"
        assert str(make_lexicon("2026.2", active=False)) == "2026.2"


class TestQuestion:
    def test_code_is_unique_within_a_lexicon(self) -> None:
        lexicon = make_lexicon()
        make_question(lexicon, "acidity")
        with pytest.raises(IntegrityError):
            make_question(lexicon, "acidity")

    def test_the_same_code_may_appear_in_another_version(self) -> None:
        """Versions are independent; a code is how they line up."""
        make_question(make_lexicon("one"), "acidity")
        make_question(make_lexicon("two"), "acidity")

    def test_rejects_an_unknown_wine_type(self) -> None:
        question = make_question(make_lexicon(), wine_types=["chardonnay"])
        with pytest.raises(ValidationError) as exc:
            question.full_clean()
        assert "wine_types" in exc.value.message_dict

    def test_phase_index_follows_the_running_order(self) -> None:
        lexicon = make_lexicon()
        assert make_question(lexicon, "a", phase=Phase.LOOK).phase_index == 0
        assert make_question(lexicon, "b", phase=Phase.CONCLUDE).phase_index == 3

    def test_applies_to_reads_its_own_wine_types(self) -> None:
        question = make_question(make_lexicon(), wine_types=[WineType.STILL_RED])
        assert question.applies_to(WineType.STILL_RED) is True
        assert question.applies_to(WineType.ROSE) is False


class TestOption:
    def test_code_is_unique_within_a_question(self) -> None:
        question = make_question(make_lexicon())
        make_option(question, "clear")
        with pytest.raises(IntegrityError):
            make_option(question, "clear")

    def test_str_names_the_category_of_a_descriptor(self) -> None:
        question = make_question(make_lexicon(), control="multi")
        citrus = make_option(question, "citrus", label="Citrus fruit")
        lemon = make_option(question, "lemon", label="Lemon", parent=citrus)
        assert str(citrus) == "Citrus fruit"
        assert str(lemon) == "Citrus fruit › Lemon"

    def test_rejects_a_parent_from_another_question(self) -> None:
        lexicon = make_lexicon()
        elsewhere = make_option(make_question(lexicon, "other"), "citrus")
        orphan = make_option(make_question(lexicon, "aromas"), "lemon")
        orphan.parent = elsewhere
        with pytest.raises(ValidationError) as exc:
            orphan.full_clean()
        assert "parent" in exc.value.message_dict

    def test_rejects_nesting_deeper_than_one_level(self) -> None:
        """A taster holding a glass cannot navigate a taxonomy."""
        question = make_question(make_lexicon(), control="multi")
        citrus = make_option(question, "citrus")
        lemon = make_option(question, "lemon", parent=citrus)
        deeper = make_option(question, "meyer_lemon", parent=lemon)
        with pytest.raises(ValidationError) as exc:
            deeper.full_clean()
        assert "parent" in exc.value.message_dict

    def test_rejects_an_unknown_wine_type(self) -> None:
        option = make_option(make_question(make_lexicon()), wine_types=["nonsense"])
        with pytest.raises(ValidationError) as exc:
            option.full_clean()
        assert "wine_types" in exc.value.message_dict
