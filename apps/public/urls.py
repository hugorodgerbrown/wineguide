"""apps/public/urls.py — URL patterns for the public site."""

from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("pick/", views.wine_pick, name="wine_pick"),
]
