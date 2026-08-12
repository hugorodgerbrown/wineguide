"""tests/conftest.py — Shared pytest fixtures."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.fixture
def htmx_client() -> Client:
    """A test client whose every request looks like an HTMX request.

    ``HX-Request: true`` is the header django-htmx's middleware reads to set
    ``request.htmx``, so this is what distinguishes a fragment request from a
    plain browser one.
    """
    return Client(headers={"hx-request": "true"})
