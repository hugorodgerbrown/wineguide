"""apps/accounts/urls.py — Sign-in URLs."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-in/<str:token>/", views.verify, name="verify"),
    path("sign-out/", views.sign_out, name="sign_out"),
]
