"""
apps/tastings/api.py — The two JSON endpoints the session client talks to.

Two endpoints is not enough to justify Django REST Framework: its serialisers,
viewsets and content negotiation would be more machinery than the thing they
wrap, and every one of them is a layer between a bug and the person reading
the code. Plain views, explicit parsing, explicit errors.

    GET  /api/lexicon/<wine_type>/   the whole question set for a style
    POST /api/sessions/              upsert one session, wholesale

The upsert is the interesting one. The client owns a session while it is being
tasted: it mints the uuid, holds state locally, and pushes the whole thing —
every answer, not a delta — whenever it can. That makes the endpoint
idempotent, which is what lets an offline queue retry blindly without
tracking what it has already sent.

Conflicts are settled by `client_updated_at`, the client's own clock. An
arriving write older than what is stored is *acknowledged and ignored*, and
the response says so, rather than erroring. A phone that spent three phases
offline and a second tab that saved a stale copy will both retry; only the
newer one should win, and neither should see a failure it has no way to act
on.
"""

from __future__ import annotations

import json
import uuid as uuid_lib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from apps.core.enums import Phase, SessionStatus, WineType
from apps.lexicon.models import Lexicon
from apps.lexicon.payload import build_payload

from .models import PhaseResponse, TastingSession


def json_login_required(
    view: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Require a signed-in user, answering with 401 JSON rather than a redirect.

    `login_required` sends a 302 to the sign-in page. The only caller here is
    `fetch`, which follows the redirect and hands the client a chunk of HTML
    where it expected JSON — a parse error, several layers from the actual
    problem. A 401 the client can act on is worth the six lines.
    """

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sign-in required"}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


class PayloadError(Exception):
    """A request body that cannot be acted on.

    Carries the field at fault so the client can point at it — this API's only
    consumer is our own code, and a message naming the field turns a
    ten-minute debugging session into a ten-second one.
    """

    def __init__(self, message: str, field: str = "") -> None:
        """Record the message and the field at fault."""
        super().__init__(message)
        self.message = message
        self.field = field


def _error(exc: PayloadError, status: int = 400) -> JsonResponse:
    """Render a `PayloadError` as JSON."""
    return JsonResponse({"error": exc.message, "field": exc.field}, status=status)


def _require(body: dict[str, Any], key: str) -> Any:
    """Return ``body[key]`` or raise `PayloadError`."""
    if key not in body or body[key] in (None, ""):
        raise PayloadError(f"Missing required field: {key}", field=key)
    return body[key]


def _parse_time(body: dict[str, Any], key: str) -> datetime:
    """Parse an ISO-8601 field into an aware datetime, or raise."""
    raw = _require(body, key)
    parsed = parse_datetime(str(raw))
    if parsed is None:
        raise PayloadError(f"{key} is not an ISO-8601 timestamp", field=key)
    if parsed.tzinfo is None:
        # The client sends UTC with an offset. A naive value means somebody
        # built the timestamp by hand, and guessing a zone for it would put a
        # session hours out and silently lose a sync race.
        raise PayloadError(f"{key} must carry a UTC offset", field=key)
    return parsed


@require_GET
@json_login_required
def lexicon(request: HttpRequest, wine_type: str) -> HttpResponse:
    """Return the whole question set for one wine style.

    Fetched once per session and cached by the client, so this is allowed to
    be the one slow-ish call in the flow. Everything after it is local.

    ``?version=`` pins the answer to one published vocabulary, which is what
    reopening a note needs: a tasting recorded against 2026.1 must come back
    with the questions it was actually asked, not with whatever is current.
    Without it the active version is served, which is what a new tasting
    wants.
    """
    if wine_type not in WineType.values:
        return JsonResponse({"error": f"Unknown wine type: {wine_type}"}, status=404)

    version = request.GET.get("version", "")
    try:
        active = (
            Lexicon.objects.get(version=version)
            if version
            else Lexicon.objects.active()
        )
    except Lexicon.DoesNotExist:
        # Either the deployment has no active lexicon and cannot run a session
        # at all, or a note points at a version that has since been deleted.
        # Say so plainly rather than serving an empty payload the client would
        # render as a session with no questions.
        detail = f"No lexicon {version}" if version else "No active lexicon"
        return JsonResponse({"error": detail}, status=503)

    response = JsonResponse(build_payload(active, wine_type))
    # Private, not public: the payload is the same for every taster, but the
    # endpoint is behind login and a shared cache has no business holding a
    # response served under a session cookie. The client and the service
    # worker do the real caching.
    response["Cache-Control"] = "private, max-age=3600"
    return response


def _parse_responses(raw: Any) -> list[dict[str, Any]]:
    """Validate the answers array.

    Args:
        raw: The ``responses`` value from the request body.

    Returns:
        The validated entries.

    Raises:
        PayloadError: If the array or any entry is malformed.

    """
    if not isinstance(raw, list):
        raise PayloadError("responses must be a list", field="responses")

    seen: set[str] = set()
    parsed = []
    for index, entry in enumerate(raw):
        where = f"responses[{index}]"
        if not isinstance(entry, dict):
            raise PayloadError(f"{where} must be an object", field=where)

        code = entry.get("question")
        if not code or not isinstance(code, str):
            raise PayloadError(f"{where}.question is required", field=where)
        if code in seen:
            # The database constraint would catch this, but as an
            # IntegrityError halfway through a transaction rather than as an
            # answerable message.
            raise PayloadError(f"{where}.question is a duplicate: {code}", field=where)
        seen.add(code)

        phase = entry.get("phase")
        if phase not in Phase.values:
            raise PayloadError(f"{where}.phase is not a phase: {phase}", field=where)

        values = entry.get("values", [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise PayloadError(f"{where}.values must be a list of strings", field=where)

        parsed.append(
            {
                "question_code": code,
                "phase": phase,
                "values": values,
                "skipped": bool(entry.get("skipped", False)),
            }
        )
    return parsed


def _session_state(session: TastingSession, *, applied: bool) -> dict[str, Any]:
    """Build the response body for a sync."""
    return {
        "uuid": str(session.uuid),
        "status": session.status,
        "applied": applied,
        "client_updated_at": session.client_updated_at.isoformat(),
        "url": session.get_absolute_url(),
    }


@dataclass(frozen=True, slots=True)
class SyncRequest:
    """A validated sync body.

    Parsing is separated from persisting so each half is one readable thing.
    Everything on here has already been checked; nothing downstream re-validates.
    """

    uuid: uuid_lib.UUID
    wine_type: str
    status: str
    started_at: datetime
    client_updated_at: datetime
    lexicon: Lexicon
    responses: list[dict[str, Any]]
    wine: dict[str, Any]
    actual: dict[str, Any]


def _parse_sync_body(body: dict[str, Any]) -> SyncRequest:
    """Validate a sync body.

    Args:
        body: The decoded request body.

    Returns:
        The validated request.

    Raises:
        PayloadError: On the first thing that is wrong, naming the field.

    """
    try:
        # Parsed rather than passed through: a malformed value reaching the
        # UUIDField lookup raises ValidationError, which is a 500.
        uuid = uuid_lib.UUID(str(_require(body, "uuid")))
    except ValueError:
        raise PayloadError("uuid is not a UUID", field="uuid") from None

    wine_type = _require(body, "wine_type")
    if wine_type not in WineType.values:
        raise PayloadError(f"Unknown wine type: {wine_type}", field="wine_type")

    status = body.get("status", SessionStatus.IN_PROGRESS)
    if status not in SessionStatus.values:
        raise PayloadError(f"Unknown status: {status}", field="status")

    version = _require(body, "lexicon_version")
    try:
        lexicon_obj = Lexicon.objects.get(version=version)
    except Lexicon.DoesNotExist:
        raise PayloadError(
            f"Unknown lexicon version: {version}", field="lexicon_version"
        ) from None

    return SyncRequest(
        uuid=uuid,
        wine_type=wine_type,
        status=status,
        started_at=_parse_time(body, "started_at"),
        client_updated_at=_parse_time(body, "client_updated_at"),
        lexicon=lexicon_obj,
        responses=_parse_responses(body.get("responses", [])),
        wine=body.get("wine") or {},
        actual=body.get("actual") or {},
    )


def _apply(session: TastingSession, parsed: SyncRequest) -> TastingSession:
    """Write a validated request onto a session and save it."""
    session.lexicon = parsed.lexicon
    session.wine_type = parsed.wine_type
    session.wine_name = str(parsed.wine.get("name", ""))[:200]
    session.producer = str(parsed.wine.get("producer", ""))[:200]
    session.region = str(parsed.wine.get("region", ""))[:200]
    session.vintage = parsed.wine.get("vintage") or None
    session.tasted_blind = bool(parsed.wine.get("blind", False))
    session.actual_grape = str(parsed.actual.get("grape", ""))[:120]
    session.actual_origin = str(parsed.actual.get("origin", ""))[:120]
    session.status = parsed.status
    session.started_at = parsed.started_at
    session.client_updated_at = parsed.client_updated_at
    if parsed.status == SessionStatus.COMPLETED and session.completed_at is None:
        session.completed_at = parsed.client_updated_at
    session.save()

    # Wholesale replacement, not a merge. The client sends its complete answer
    # set every time, so anything not in this body was deliberately removed —
    # a merge would resurrect it.
    session.responses.all().delete()
    PhaseResponse.objects.bulk_create(
        [PhaseResponse(session=session, **entry) for entry in parsed.responses]
    )
    session.sync_denormalised_fields()
    return session


@require_POST
@json_login_required
@transaction.atomic
def sync(request: HttpRequest) -> HttpResponse:
    """Create or replace one session from the client's copy.

    Idempotent on ``uuid``: replaying the same body changes nothing. An older
    ``client_updated_at`` than the stored one is acknowledged with
    ``applied: false`` and discarded.
    """
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _error(PayloadError("Body is not valid JSON"))
    if not isinstance(body, dict):
        return _error(PayloadError("Body must be a JSON object"))

    try:
        parsed = _parse_sync_body(body)
    except PayloadError as exc:
        return _error(exc)

    # select_for_update so two tabs syncing the same session serialise rather
    # than interleaving a read-compare-write.
    existing = (
        TastingSession.objects.select_for_update().filter(uuid=parsed.uuid).first()
    )
    if existing is not None:
        if existing.user_id != request.user.pk:
            # 404, not 403: confirming that a uuid exists tells a stranger
            # something about someone else's journal.
            return JsonResponse({"error": "Not found"}, status=404)
        if existing.client_updated_at >= parsed.client_updated_at:
            return JsonResponse(_session_state(existing, applied=False))

    # `json_login_required` has already rejected an anonymous request, but
    # mypy sees the union on request.user and cannot know that.
    assert request.user.is_authenticated  # noqa: S101
    session = _apply(
        existing or TastingSession(uuid=parsed.uuid, user=request.user), parsed
    )
    return JsonResponse(_session_state(session, applied=True), status=200)
