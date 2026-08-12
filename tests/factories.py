"""
tests/factories.py — Test data builders.

Deliberately plain functions rather than factory_boy: the object graph here is
small and shallow, and a factory library would be one more thing to learn
before writing a test. Revisit if the graph grows.
"""

from __future__ import annotations

import itertools
import uuid as uuid_lib
from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

from apps.core.enums import Control, Phase, SessionStatus, WineType
from apps.lexicon.models import Lexicon, Option, Question
from apps.tastings.models import PhaseResponse, TastingSession

NOW = datetime(2026, 3, 4, 19, 30, tzinfo=UTC)

# Unique-by-default names. A test that creates two sessions without naming
# their users should get two users, not a collision on the second one.
_counter = itertools.count(1)


def make_user(email: str = "") -> User:
    """Create a taster, with a unique email unless one is given."""
    email = email or f"taster{next(_counter)}@example.com"
    return get_user_model().objects.create_user(username=email, email=email)


def make_lexicon(version: str = "", *, active: bool = True) -> Lexicon:
    """Create a lexicon with no questions.

    Deactivates any existing active lexicon first, so a test that wants two
    lexicons does not trip the one-active constraint by accident.
    """
    if active:
        Lexicon.objects.filter(is_active=True).update(is_active=False)
    return Lexicon.objects.create(
        version=version or f"test.{next(_counter)}", is_active=active
    )


def make_question(
    lexicon: Lexicon,
    code: str = "clarity",
    *,
    phase: str = Phase.LOOK,
    control: str = Control.SINGLE,
    wine_types: list[str] | None = None,
    order: int = 0,
    prompt: str = "",
) -> Question:
    """Create a question on ``lexicon``."""
    return Question.objects.create(
        lexicon=lexicon,
        code=code,
        phase=phase,
        control=control,
        prompt=prompt or f"Prompt for {code}",
        wine_types=wine_types or [],
        order=order,
    )


def make_option(
    question: Question,
    code: str = "clear",
    *,
    label: str = "",
    parent: Option | None = None,
    swatch: str = "",
    wine_types: list[str] | None = None,
    order: int = 0,
) -> Option:
    """Create an option on ``question``."""
    return Option.objects.create(
        question=question,
        parent=parent,
        code=code,
        label=label or code.replace("_", " ").title(),
        swatch=swatch,
        wine_types=wine_types or [],
        order=order,
    )


def make_session(
    user: User | None = None,
    lexicon: Lexicon | None = None,
    *,
    wine_type: str = WineType.STILL_RED,
    status: str = SessionStatus.IN_PROGRESS,
    uuid: uuid_lib.UUID | None = None,
    client_updated_at: datetime | None = None,
    **kwargs: object,
) -> TastingSession:
    """Create a tasting session, filling in whatever was not specified."""
    return TastingSession.objects.create(
        uuid=uuid or uuid_lib.uuid4(),
        user=user or make_user(),
        lexicon=lexicon or make_lexicon(),
        wine_type=wine_type,
        status=status,
        started_at=NOW,
        client_updated_at=client_updated_at or NOW,
        **kwargs,
    )


def make_response(
    session: TastingSession,
    question_code: str,
    values: list[str],
    *,
    phase: str = Phase.LOOK,
    skipped: bool = False,
) -> PhaseResponse:
    """Record an answer on ``session``."""
    return PhaseResponse.objects.create(
        session=session,
        phase=phase,
        question_code=question_code,
        values=values,
        skipped=skipped,
    )
