"""Tests for the landing page.

The page has no moving parts, so these assert the two things that can quietly
rot: that the sequence it advertises is the one the session runs, and that the
call to action sends a signed-in taster somewhere different from a stranger.
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.enums import PHASE_ORDER, Phase
from apps.public.views import PHASE_BLURBS
from tests.factories import make_user

HOME = reverse("public:home")


class TestHome:
    def test_renders(self, client: Client) -> None:
        response = client.get(HOME)
        assert response.status_code == 200

    def test_uses_the_home_template(self, client: Client) -> None:
        names = [t.name for t in client.get(HOME).templates]
        assert "public/home.html" in names
        assert "base.html" in names

    def test_leads_on_learning_to_taste(self, client: Client) -> None:
        assert "Learn to taste like a sommelier" in client.get(HOME).content.decode()

    def test_lists_every_phase_in_running_order(self, client: Client) -> None:
        """The page advertises the method; if a phase were added to the
        session and not here, the page would be describing a different app.
        """
        content = client.get(HOME).content.decode()
        positions = [content.index(str(Phase(code).label)) for code in PHASE_ORDER]
        assert positions == sorted(positions)

    def test_every_phase_has_a_blurb(self) -> None:
        assert set(PHASE_BLURBS) == set(PHASE_ORDER)


class TestCallToAction:
    @pytest.mark.django_db
    def test_a_signed_in_taster_is_sent_to_a_new_tasting(self, client: Client) -> None:
        client.force_login(make_user())
        content = client.get(HOME).content.decode()
        assert reverse("tastings:start_new") in content

    def test_a_stranger_is_sent_to_sign_in(self, client: Client) -> None:
        content = client.get(HOME).content.decode()
        assert reverse("accounts:sign_in") in content
        assert reverse("tastings:start_new") not in content
