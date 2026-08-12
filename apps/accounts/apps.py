"""apps/accounts/apps.py — App configuration for sign-in."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Passwordless sign-in. No profile, no social features (PRD §6.4)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"
