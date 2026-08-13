"""
End-to-end tests for the homepage and the theme toggle.

The homepage is plain HTML now, so most of what it does is covered far more
cheaply in `tests/public`. What is left here is the part that needs a real
browser: that the theme toggle appears only when scripting is available, and
that a reader's choice survives a reload.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.django_db


class TestHomepage:
    def test_leads_on_learning_to_taste(self, home: Page) -> None:
        expect(home.get_by_role("heading", level=1)).to_contain_text(
            "Learn to taste like a sommelier"
        )

    def test_reads_the_same_without_javascript(self, no_js_page: Page) -> None:
        """Nothing on this page is an enhancement, so nothing on it may
        depend on scripting (CLAUDE.md, invariant 3).
        """
        expect(no_js_page.get_by_role("heading", level=1)).to_contain_text(
            "Learn to taste like a sommelier"
        )
        expect(
            no_js_page.get_by_role("link", name="Start a tasting").first
        ).to_be_visible()


class TestThemeToggle:
    def test_is_revealed_by_javascript(self, home: Page) -> None:
        expect(home.get_by_role("button", name="Dark mode")).to_be_visible()

    def test_stays_hidden_without_javascript(self, no_js_page: Page) -> None:
        expect(no_js_page.get_by_role("button", name="Dark mode")).to_be_hidden()

    def test_switches_the_theme(self, home: Page) -> None:
        toggle = home.get_by_role("button", name="Dark mode")

        toggle.click()

        expect(home.locator("html")).to_have_attribute("data-theme", "dark")
        expect(toggle).to_have_attribute("aria-pressed", "true")

    def test_the_choice_survives_a_reload(self, home: Page) -> None:
        home.get_by_role("button", name="Dark mode").click()
        expect(home.locator("html")).to_have_attribute("data-theme", "dark")

        home.reload()

        expect(home.locator("html")).to_have_attribute("data-theme", "dark")
