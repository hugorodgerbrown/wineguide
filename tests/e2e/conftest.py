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
from playwright.sync_api import Browser, Page
from pytest_django.live_server_helper import LiveServer


@pytest.fixture
def home(live_server: LiveServer, page: Page) -> Page:
    """A page already on the homepage, with the JS loaded."""
    page.goto(live_server.url)
    return page


@pytest.fixture
def no_js_page(live_server: LiveServer, browser: Browser) -> Iterator[Page]:
    """A page with JavaScript disabled, for the progressive-enhancement path.

    The site's one interactive control is a plain link that HTMX upgrades. With
    scripting off it must still navigate, which is what this fixture exists to
    prove.
    """
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(live_server.url)
    yield page
    context.close()
