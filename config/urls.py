"""config/urls.py — Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

from apps.core import views as core_views

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    # At the root, not under /static/: a service worker can only control pages
    # at or below its own path. See apps/core/views.py.
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("offline/", core_views.offline, name="offline"),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    # The guided session: one page, driven client-side.
    path("taste/", include("apps.tastings.urls", namespace="tastings")),
    # Its two JSON endpoints, mounted under their own prefix so the service
    # worker can tell pages and API responses apart by URL alone.
    path("api/", include("apps.tastings.api_urls", namespace="tastings_api")),
    path("journal/", include("apps.journal.urls", namespace="journal")),
    path("", include("apps.public.urls", namespace="public")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
