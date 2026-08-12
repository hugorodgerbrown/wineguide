"""Tests for the wine data module."""

from __future__ import annotations

import pytest

from apps.public.wines import WINES, Wine, wine_at


class TestWineAt:
    def test_returns_the_wine_at_the_index(self) -> None:
        assert wine_at(0) is WINES[0]
        assert wine_at(2) is WINES[2]

    def test_wraps_past_the_end(self) -> None:
        assert wine_at(len(WINES)) is WINES[0]
        assert wine_at(len(WINES) + 1) is WINES[1]

    def test_wraps_from_the_end_for_negative_indices(self) -> None:
        assert wine_at(-1) is WINES[-1]

    @pytest.mark.parametrize("index", [0, 7, 41, -3, 10**9])
    def test_always_returns_a_wine(self, index: int) -> None:
        assert isinstance(wine_at(index), Wine)


class TestWine:
    def test_title_reads_as_producer_name_vintage(self) -> None:
        wine = Wine(
            name="Chablis",
            producer="Domaine X",
            region="Burgundy",
            country="France",
            year=2021,
            grape="Chardonnay",
            note="",
        )
        assert wine.title == "Domaine X Chablis 2021"

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            WINES[0].year = 1999  # type: ignore[misc]


class TestSeedData:
    def test_every_wine_is_populated(self) -> None:
        for wine in WINES:
            assert wine.name
            assert wine.producer
            assert wine.region
            assert wine.country
            assert wine.grape
            assert wine.note
            assert 1900 < wine.year < 2100

    def test_the_rotation_has_no_duplicates(self) -> None:
        titles = [wine.title for wine in WINES]
        assert len(titles) == len(set(titles))
