"""
apps/journal/filters.py — Turning query parameters into a filtered queryset.

Separated from the view so the rules can be tested without a request, and so
the list view and its HTMX fragment cannot drift apart — they both call this.

Every filter is forgiving. A journal search that returns an error page because
someone typed a letter into the year box is worse than one that quietly
ignores it: the taster is looking for a wine they half-remember, not composing
a query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Q
from django.http import QueryDict
from django.utils.dateparse import parse_date

from apps.core.enums import WineType
from apps.tastings.models import TastingSession


@dataclass(frozen=True, slots=True)
class JournalFilters:
    """The filters a request asked for, after parsing."""

    q: str = ""
    wine_type: str = ""
    grape: str = ""
    quality: str = ""
    date_from: date | None = None
    date_to: date | None = None
    #: Parameters that were present but unusable, so the template can say so
    #: rather than silently returning a list that ignores them.
    ignored: tuple[str, ...] = field(default=())

    @property
    def any_applied(self) -> bool:
        """Return whether anything is actually narrowing the list."""
        return any(
            (
                self.q,
                self.wine_type,
                self.grape,
                self.quality,
                self.date_from,
                self.date_to,
            )
        )


def parse_filters(params: QueryDict) -> JournalFilters:
    """Read filters out of a query string.

    Args:
        params: ``request.GET``.

    Returns:
        The parsed filters, with anything unusable recorded in ``ignored``.

    """
    ignored: list[str] = []

    wine_type = (params.get("wine_type") or "").strip()
    if wine_type and wine_type not in WineType.values:
        ignored.append("wine_type")
        wine_type = ""

    def _date(key: str) -> date | None:
        raw = (params.get(key) or "").strip()
        if not raw:
            return None
        parsed = parse_date(raw)
        if parsed is None:
            ignored.append(key)
        return parsed

    date_from = _date("date_from")
    date_to = _date("date_to")

    return JournalFilters(
        q=(params.get("q") or "").strip(),
        wine_type=wine_type,
        grape=(params.get("grape") or "").strip(),
        quality=(params.get("quality") or "").strip(),
        date_from=date_from,
        date_to=date_to,
        ignored=tuple(ignored),
    )


def apply_filters(queryset, filters: JournalFilters):  # type: ignore[no-untyped-def]
    """Narrow ``queryset`` by ``filters``.

    The grape filter matches either side of the guess: a taster looking back
    for "everything I thought was Nebbiolo" and one looking for "everything
    that actually was" are both plausible, and asking them to pick a mode
    before searching is asking them to think about our schema.

    Args:
        queryset: A `TastingSession` queryset, already scoped to one user.
        filters: The parsed filters.

    Returns:
        The narrowed queryset.

    """
    if filters.q:
        queryset = queryset.filter(
            Q(wine_name__icontains=filters.q)
            | Q(producer__icontains=filters.q)
            | Q(region__icontains=filters.q)
            | Q(actual_grape__icontains=filters.q)
        )
    if filters.wine_type:
        queryset = queryset.filter(wine_type=filters.wine_type)
    if filters.grape:
        queryset = queryset.filter(
            Q(guessed_grape__iexact=filters.grape)
            | Q(actual_grape__icontains=filters.grape)
        )
    if filters.quality:
        queryset = queryset.filter(quality=filters.quality)
    if filters.date_from:
        queryset = queryset.filter(started_at__date__gte=filters.date_from)
    if filters.date_to:
        queryset = queryset.filter(started_at__date__lte=filters.date_to)
    return queryset


def visible_sessions(user) -> "TastingSession.objects":  # type: ignore[no-untyped-def,valid-type]
    """Return the sessions ``user`` may see.

    Every journal view starts here. Tasting notes are personal (PRD §8), and
    a scoping filter applied at each call site is one that will eventually be
    forgotten at one of them.
    """
    return TastingSession.objects.for_user(user).select_related("lexicon")
