"""
apps/public/wines.py — The seed set of wine picks shown on the homepage.

A hard-coded tuple rather than a model: there is nothing to edit, query or
migrate yet, and a constant keeps the homepage free of a database round-trip.
Replace this module with a model + queryset when picks become editable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Wine:
    """One wine pick, as rendered in the homepage panel."""

    name: str
    producer: str
    region: str
    country: str
    year: int
    grape: str
    note: str

    @property
    def title(self) -> str:
        """Producer, wine and vintage on one line, for headings and titles."""
        return f"{self.producer} {self.name} {self.year}"


WINES: tuple[Wine, ...] = (
    Wine(
        name="Chablis Premier Cru Montée de Tonnerre",
        producer="Domaine Louis Michel",
        region="Burgundy",
        country="France",
        year=2021,
        grape="Chardonnay",
        note=(
            "Unoaked and taut, with wet-stone bite behind the citrus. Drink it "
            "cold but not iced, or the texture disappears."
        ),
    ),
    Wine(
        name="Barolo Cannubi",
        producer="Paolo Scavino",
        region="Piedmont",
        country="Italy",
        year=2018,
        grape="Nebbiolo",
        note=(
            "Tar, dried rose and a tannic frame that wants either a decade in "
            "the cellar or a plate of braised beef tonight."
        ),
    ),
    Wine(
        name="Riesling Kabinett Sonnenuhr",
        producer="Joh. Jos. Prüm",
        region="Mosel",
        country="Germany",
        year=2022,
        grape="Riesling",
        note=(
            "Barely 8% alcohol and all the better for it: green apple, slate "
            "and a sweetness the acidity keeps in check."
        ),
    ),
    Wine(
        name="Rioja Gran Reserva 904",
        producer="La Rioja Alta",
        region="Rioja",
        country="Spain",
        year=2015,
        grape="Tempranillo",
        note=(
            "Four years in American oak, and it still tastes of fruit — dried "
            "cherry, leather, vanilla, and a finish that keeps going."
        ),
    ),
    Wine(
        name="Assyrtiko",
        producer="Domaine Sigalas",
        region="Santorini",
        country="Greece",
        year=2023,
        grape="Assyrtiko",
        note=(
            "Volcanic soil, sea salt and lemon pith. The white to reach for "
            "when Sauvignon Blanc has started to bore you."
        ),
    ),
)


def wine_at(index: int) -> Wine:
    """Return the pick at ``index``, wrapping around the end of the list.

    Wrapping (rather than raising) is what lets the "another one" control be a
    plain incrementing link: the caller never has to know how many picks
    exist, and a bookmarked out-of-range index still renders a page.

    Args:
        index: Any integer; negative values wrap from the end.

    Returns:
        The wine at that position in the rotation.

    """
    return WINES[index % len(WINES)]
