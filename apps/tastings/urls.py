"""apps/tastings/urls.py — The guided session."""

from django.urls import path

from . import views

app_name = "tastings"

urlpatterns = [
    # One URL for the whole session. Everything after this is client-side —
    # see the module docstring in views.py for why.
    path("", views.start, name="start"),
]
