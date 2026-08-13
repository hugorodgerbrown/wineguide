"""
End-to-end tests for the journal.

The journal is where the HTMX swap and the no-JavaScript path now live — the
homepage used to carry both, on a wine picker that no longer exists. Two
response shapes, one view, and the only way to prove the pair is a real
browser with scripting on and then off.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from playwright.sync_api import Browser, Page, expect
from pytest_django.live_server_helper import LiveServer

from apps.tastings.models import TastingSession
from tests.e2e.conftest import sign_in
from tests.factories import make_lexicon, make_session, make_user

pytestmark = pytest.mark.django_db


class TestRowDelete:
    def test_htmx_removes_the_row_without_navigating(self, journal: Page) -> None:
        rows = journal.locator("#journal-results li")
        expect(rows).to_have_count(2)
        before = journal.url

        journal.once("dialog", lambda dialog: dialog.accept())
        journal.get_by_role("button", name="Delete").first.click()

        expect(rows).to_have_count(1)
        assert journal.url == before

    def test_the_delete_is_real(self, journal: Page) -> None:
        journal.once("dialog", lambda dialog: dialog.accept())
        journal.get_by_role("button", name="Delete").first.click()
        expect(journal.locator("#journal-results li")).to_have_count(1)

        assert TastingSession.objects.count() == 1

    def test_declining_the_confirmation_keeps_the_row(self, journal: Page) -> None:
        journal.once("dialog", lambda dialog: dialog.dismiss())
        journal.get_by_role("button", name="Delete").first.click()

        expect(journal.locator("#journal-results li")).to_have_count(2)
        assert TastingSession.objects.count() == 2

    def test_works_without_javascript(
        self, live_server: LiveServer, browser: Browser
    ) -> None:
        """No HTMX, so the form posts and the view redirects — and there is no
        confirmation, which is the same bargain the detail page has always
        made.
        """
        lexicon = make_lexicon("2026.1")
        user = make_user()
        make_session(user, lexicon)
        make_session(user, lexicon)

        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        try:
            sign_in(page, live_server, user)
            page.goto(live_server.url + reverse("journal:list"))
            expect(page.locator("#journal-results li")).to_have_count(2)

            page.get_by_role("button", name="Delete").first.click()

            expect(page.locator("#journal-results li")).to_have_count(1)
            assert TastingSession.objects.count() == 1
        finally:
            context.close()


class TestFilters:
    def test_searching_swaps_the_results_in_place(self, journal: Page) -> None:
        """The debounce fires on input, so no submit is needed — and the
        heading stays put, which is what tells you the page did not reload.
        """
        journal.get_by_placeholder("Wine, producer, region or grape").fill("nothing")

        expect(journal.locator("#journal-results")).to_contain_text(
            "Nothing matches those filters"
        )
        expect(journal.get_by_role("heading", level=1)).to_contain_text("Journal")
