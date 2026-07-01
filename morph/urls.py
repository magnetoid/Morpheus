"""
Morpheus — URL Configuration

Django is a runtime, not a UI. The merchant-facing surface lives at
`/dashboard/...` (provided by the `admin_dashboard` plugin); Django's
own admin at `/admin/` is only mounted when `DEBUG=True` so it isn't
exposed in production.

Plugin URLs are injected at runtime by the plugin registry.
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView


def _healthz(_request):
    """Liveness probe — always returns 200 once the WSGI app has loaded.

    Hit by the Docker compose healthcheck (curl http://localhost:8000/healthz)
    AND by Coolify's optional app-level healthcheck. Must be:
      - Fast (no DB / Redis / network).
      - Stable (the URL never changes; integrations bake it in).
      - Exempt from SECURE_SSL_REDIRECT (see settings.SECURE_REDIRECT_EXEMPT)
        so the in-container check doesn't bounce to https://localhost which
        has no TLS listener.

    Real readiness — "can serve plugin URLs / DB / Redis" — lives at
    /api/ready/ from the api plugin. This endpoint is for "the python
    process answers HTTP", which is enough for orchestrators to start
    forwarding traffic but NOT enough to declare a release healthy.
    """
    return HttpResponse('ok', content_type='text/plain', status=200)


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
    # Liveness probe. First in the list so middleware ordering can't
    # accidentally bury it behind a slow lookup. Returns 200 'ok' the
    # moment the WSGI app is loaded.
    path('healthz', _healthz),
    path('healthz/', _healthz),
    # The Assistant lives in core and mounts at /dashboard/assistant/.
    path('dashboard/assistant/', include('core.assistant.urls', namespace='assistant')),
    # Error capture + dashboard surface — /api/errors/client/ ingest and
    # /dashboard/errors/ list.
    path('', include('core.errors.urls', namespace='errors')),
    path('', include('api.urls')),  # GraphQL at /graphql/
    # Auth lives at /auth/. /accounts/* is kept as a 301-redirect for any
    # external bookmark or third-party doc that still references it.
    # Passwordless OTP lives at /auth/otp/ alongside allauth's flows.
    path('auth/otp/', include('core.auth.urls', namespace='core_auth')),
    path('auth/', include('allauth.urls')),
    re_path(
        r'^accounts/(?P<rest>.*)$',
        RedirectView.as_view(url='/auth/%(rest)s', permanent=True, query_string=True),
    ),
    # set_language view (the storefront language switcher POSTs here). Unprefixed.
    path('i18n/', include('django.conf.urls.i18n')),
    # Chrome surfaces (dashboard/, api/, payments/, …) — never language-prefixed.
    path('', include('plugins.chrome_urls')),
]

# Storefront pages are language-routed: the core language (LANGUAGE_CODE) is
# served unprefixed, every other enabled language gets a /<code>/ prefix
# (ADR 0022). Only prefix='' (storefront) plugin URLs are wrapped — dashboard,
# api and payments above stay unprefixed. Appended last so the storefront
# catch-all never shadows chrome routes.
urlpatterns += i18n_patterns(
    path('', include('plugins.storefront_urls')),
    prefix_default_language=False,
)

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
    # Production: serve uploaded media through Django so the volume-backed
    # /app/media/ files are reachable at /media/<path>. Cloudflare/CDN
    # caches them in front; gunicorn only sees the cold misses. Add a real
    # static-asset edge (Plesk alias, S3, R2) when traffic justifies it.
    from django.views.static import serve as _serve

    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', _serve, {'document_root': settings.MEDIA_ROOT}),
    ]
    # Production: register a stub `admin` namespace so `reverse('admin:login')`
    # — used by Django's @staff_member_required decorator — works without the
    # full admin app being mounted.
    urlpatterns.insert(
        0,
        path('admin/', include((_admin_alias_patterns, 'admin'), namespace='admin')),
    )
