"""Tests for the public site views."""

from __future__ import annotations

import pytest
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse

from apps.public.wines import WINES, Wine, wine_at

HOME = reverse("public:home")
PICK = reverse("public:wine_pick")


class TestHome:
    def test_renders(self, client: Client) -> None:
        response = client.get(HOME)
        assert response.status_code == 200

    def test_uses_the_home_template_and_the_panel_partial(self, client: Client) -> None:
        response = client.get(HOME)
        names = [template.name for template in response.templates]
        assert "public/home.html" in names
        assert "public/_wine_panel.html" in names
        assert "base.html" in names

    def test_shows_the_first_wine(self, client: Client) -> None:
        response = client.get(HOME)
        assert WINES[0].producer in response.content.decode()

    def test_offers_the_next_pick_as_a_real_link(self, client: Client) -> None:
        """The control must work with no JavaScript, so it needs an href."""
        content = client.get(HOME).content.decode()
        assert f'href="{PICK}?index=1"' in content
        assert f'hx-get="{PICK}?index=1"' in content

    def test_loads_htmx(self, client: Client) -> None:
        assert "js/vendor/htmx.min.js" in client.get(HOME).content.decode()

    def test_title_is_just_the_site_name(self, client: Client) -> None:
        """The homepage IS the site, so _page_meta must not double it up."""
        content = client.get(HOME).content.decode()
        assert "Wineguide · Wineguide" not in content

    def test_renders_the_theme_toggle_hidden(self, client: Client) -> None:
        """Hidden until theme.js reveals it — a dead control should not show."""
        content = client.get(HOME).content.decode()
        assert 'id="theme-toggle"' in content
        assert "hidden" in content


class TestWinePick:
    def test_htmx_request_gets_only_the_panel(self, htmx_client: Client) -> None:
        response = htmx_client.get(PICK, {"index": 1})
        names = [template.name for template in response.templates]
        assert names == ["public/_wine_panel.html"]
        assert b"<!DOCTYPE html>" not in response.content

    def test_plain_request_gets_the_whole_page(self, client: Client) -> None:
        response = client.get(PICK, {"index": 1})
        names = [template.name for template in response.templates]
        assert "public/home.html" in names
        assert b"<!DOCTYPE html>" in response.content

    def test_serves_the_requested_wine(self, htmx_client: Client) -> None:
        content = htmx_client.get(PICK, {"index": 2}).content.decode()
        assert WINES[2].producer in content

    def test_advances_the_index_for_the_next_request(self, htmx_client: Client) -> None:
        content = htmx_client.get(PICK, {"index": 2}).content.decode()
        assert f'hx-get="{PICK}?index=3"' in content

    def test_index_wraps_past_the_end_of_the_rotation(
        self, htmx_client: Client
    ) -> None:
        content = htmx_client.get(PICK, {"index": len(WINES)}).content.decode()
        assert WINES[0].producer in content

    @pytest.mark.parametrize("index", ["", "not-a-number", "3.5", "1;2"])
    def test_unparseable_index_falls_back_to_the_first_wine(
        self, htmx_client: Client, index: str
    ) -> None:
        """The index is a position in a rotation, not an identifier — a bad
        one is not an error, it just starts over.
        """
        content = htmx_client.get(PICK, {"index": index}).content.decode()
        assert WINES[0].producer in content

    def test_a_huge_index_still_renders(self, htmx_client: Client) -> None:
        response = htmx_client.get(PICK, {"index": 10**9})
        assert response.status_code == 200
        assert wine_at(10**9).producer in response.content.decode()

    def test_renders_non_ascii_copy_intact(self, htmx_client: Client) -> None:
        # WINES[2] is the Joh. Jos. Prüm Riesling.
        assert "Prüm" in htmx_client.get(PICK, {"index": 2}).content.decode()


class TestPageMeta:
    def test_appends_the_site_name_to_a_page_title(self) -> None:
        html = render_to_string(
            "includes/_page_meta.html",
            {"title": "Barolo", "description": "d", "SITE_NAME": "Wineguide"},
        )
        assert "Barolo · Wineguide" in html

    def test_does_not_repeat_a_title_that_is_the_site_name(self) -> None:
        html = render_to_string(
            "includes/_page_meta.html",
            {"title": "Wineguide", "description": "d", "SITE_NAME": "Wineguide"},
        )
        assert "Wineguide · Wineguide" not in html


class TestWinePanelTemplate:
    def test_escapes_wine_copy(self) -> None:
        """Django autoescapes by default. Asserted here so that adding |safe
        to the note is a failing test rather than a silent XSS hole.
        """
        hostile = Wine(
            name="<script>alert(1)</script>",
            producer="P",
            region="R",
            country="C",
            year=2020,
            grape="G",
            note="<img src=x onerror=alert(1)>",
        )
        html = render_to_string("public/_wine_panel.html", {"wine": hostile})
        assert "<script>" not in html
        assert "<img" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html
