"""
End-to-end tests for the homepage.

Three things need a real browser to verify, and they are the three things
here: that HTMX swaps the panel without navigating, that the same control
still works with scripting off, and that the theme toggle appears and sticks.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from apps.public.wines import WINES

pytestmark = pytest.mark.django_db


class TestHomepage:
    def test_renders_the_hero_and_the_first_pick(self, home: Page) -> None:
        expect(home.get_by_role("heading", level=1)).to_contain_text(
            "Bottles worth drinking"
        )
        expect(home.locator("#wine-panel")).to_contain_text(WINES[0].producer)


class TestWineSwap:
    def test_htmx_swaps_the_panel_in_place(self, home: Page) -> None:
        panel = home.locator("#wine-panel")
        expect(panel).to_contain_text(WINES[0].producer)

        home.get_by_role("link", name="Show me another").click()

        expect(panel).to_contain_text(WINES[1].producer)

    def test_the_swap_does_not_navigate(self, home: Page) -> None:
        """A full page load would work too, but it is not what this control is
        for — assert the URL is untouched so a lost hx-get shows up here.
        """
        before = home.url

        home.get_by_role("link", name="Show me another").click()
        expect(home.locator("#wine-panel")).to_contain_text(WINES[1].producer)

        assert home.url == before

    def test_repeated_swaps_walk_the_rotation_and_wrap(self, home: Page) -> None:
        panel = home.locator("#wine-panel")
        for wine in WINES[1:] + (WINES[0],):
            home.get_by_role("link", name="Show me another").click()
            expect(panel).to_contain_text(wine.producer)

    def test_works_without_javascript(self, no_js_page: Page) -> None:
        """No HTMX, so the link navigates — and the server returns the whole
        page rather than a bare fragment.
        """
        no_js_page.get_by_role("link", name="Show me another").click()

        expect(no_js_page.locator("#wine-panel")).to_contain_text(WINES[1].producer)
        expect(no_js_page.get_by_role("heading", level=1)).to_be_visible()
        assert "/pick/" in no_js_page.url


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

    def test_the_theme_survives_an_htmx_swap(self, home: Page) -> None:
        home.get_by_role("button", name="Dark mode").click()

        home.get_by_role("link", name="Show me another").click()
        expect(home.locator("#wine-panel")).to_contain_text(WINES[1].producer)

        expect(home.locator("html")).to_have_attribute("data-theme", "dark")
