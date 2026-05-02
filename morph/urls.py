"""
Morpheus — URL Configuration

Django is a runtime, not a UI. The merchant-facing surface lives at
`/dashboard/...` (provided by the `admin_dashboard` plugin); Django's
own admin at `/admin/` is only mounted when `DEBUG=True` so it isn't
exposed in production.

Plugin URLs are injected at runtime by the plugin registry.
"""
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView


# Fake admin namespace exposing only `admin:login` — needed because
# @staff_member_required hardcodes a redirect to that named URL. When
# DEBUG=False the real admin URLconf isn't mounted, so unauthenticated
# hits to /dashboard/* would otherwise crash with NoReverseMatch.
# Internally the alias just bounces to allauth at /auth/login/.
_admin_alias_patterns = [
    path(
        'login/',
        RedirectView.as_view(url='/auth/login/', permanent=False, query_string=True),
        name='login',
    ),
]


urlpatterns = [
    # The Assistant lives in core and mounts at /dashboard/assistant/.
    path('dashboard/assistant/', include('core.assistant.urls', namespace='assistant')),
    path('', include('api.urls')),          # GraphQL at /graphql/
    # Auth lives at /auth/. /accounts/* is kept as a 301-redirect for any
    # external bookmark or third-party doc that still references it.
    path('auth/', include('allauth.urls')),
    re_path(
        r'^accounts/(?P<rest>.*)$',
        RedirectView.as_view(url='/auth/%(rest)s', permanent=True, query_string=True),
    ),
    path('', include('plugins.urls')),
]

if settings.DEBUG:
    # Django's stock admin is only available in development as a fallback.
    # Production users go through /dashboard/ — see the `admin_dashboard`
    # plugin. If you need to inspect data on a deployed instance, use the
    # Morpheus assistant or the GraphQL admin layer, not /admin/.
    from django.contrib import admin
    urlpatterns.insert(0, path('admin/', admin.site.urls))
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Production: register a stub `admin` namespace so `reverse('admin:login')`
    # — used by Django's @staff_member_required decorator — works without the
    # full admin app being mounted.
    urlpatterns.insert(
        0,
        path('admin/', include((_admin_alias_patterns, 'admin'), namespace='admin')),
    )
