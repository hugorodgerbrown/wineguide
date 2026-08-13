"""
tests/e2e/conftest.py — Fixtures for the Playwright suite.

These tests run against a real browser and a real server, so they are the only
place the HTMX swap and the theme toggle are exercised end to end. Everything
cheaper — view behaviour, theme rules — belongs in the pytest and Vitest
suites; keep this directory to the handful of paths that genuinely need a
browser.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
from playwright.sync_api import Browser, Page
from pytest_django.live_server_helper import LiveServer

from apps.accounts.tokens import make_token
from tests.factories import make_lexicon, make_session, make_user


@pytest.fixture
def home(live_server: LiveServer, page: Page) -> Page:
    """A page already on the homepage, with the JS loaded."""
    page.goto(live_server.url)
    return page


@pytest.fixture
def no_js_page(live_server: LiveServer, browser: Browser) -> Iterator[Page]:
    """A page with JavaScript disabled, for the progressive-enhancement path.

    Everything outside the guided session must work here — that is the whole
    of invariant 3 in CLAUDE.md, and a browser is the only way to prove it.
    """
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(live_server.url)
    yield page
    context.close()


def sign_in(page: Page, live_server: LiveServer, user: AbstractUser) -> None:
    """Sign ``user`` in by following their magic link.

    The app's own front door rather than a hand-built cookie: it is one
    navigation, and it means these tests break if sign-in does.
    """
    path = reverse("accounts:verify", kwargs={"token": make_token(user)})
    page.goto(live_server.url + path)


@pytest.fixture
def journal(live_server: LiveServer, page: Page) -> Page:
    """A signed-in taster's journal, holding two notes.

    Two, because a row-level delete is only interesting when there is
    something left behind afterwards.
    """
    lexicon = make_lexicon("2026.1")
    user = make_user()
    make_session(user, lexicon)
    make_session(user, lexicon)
    sign_in(page, live_server, user)
    page.goto(live_server.url + reverse("journal:list"))
    return page
