"""apps/tastings/urls.py — The guided session."""

from django.urls import path

from . import views

app_name = "tastings"

urlpatterns = [
    # One URL for the whole session. Everything after this is client-side —
    # see the module docstring in views.py for why.
    path("", views.start, name="start"),
    # The same page, told not to resume. Two URLs rather than a query string
    # so "start a new tasting" is a link anyone can bookmark, share or hit
    # with scripting off, and so the difference is visible in the address bar
    # rather than buried in client state.
    path("new/", views.start_new, name="start_new"),
    # Reopening a stored note. The uuid is the client-generated one the
    # journal already links by, so this is reachable from a row without the
    # journal knowing anything about how a session works.
    path("<uuid:uuid>/", views.reopen, name="reopen"),
]
