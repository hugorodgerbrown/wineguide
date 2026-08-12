"""apps/journal/urls.py — Journal URLs."""

from django.urls import path

from . import views

app_name = "journal"

urlpatterns = [
    path("", views.journal_list, name="list"),
    path("<uuid:uuid>/", views.detail, name="detail"),
    path("<uuid:uuid>/edit/", views.edit, name="edit"),
    path("<uuid:uuid>/delete/", views.delete, name="delete"),
]
