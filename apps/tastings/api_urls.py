"""
apps/tastings/api_urls.py — JSON endpoints, mounted apart from the HTML views.

Kept in their own module and namespace so the service worker can match them by
prefix: pages are cached one way, API responses another, and a router that
mixes them makes that rule impossible to state.
"""

from django.urls import path

from . import api

app_name = "tastings_api"

urlpatterns = [
    path("lexicon/<str:wine_type>/", api.lexicon, name="lexicon"),
    path("sessions/", api.sync, name="sync"),
]
