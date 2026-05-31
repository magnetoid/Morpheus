"""PWA endpoints: manifest, service worker, offline fallback,
push subscribe / unsubscribe.

All public + cacheable. The service worker is served with
``Service-Worker-Allowed: /`` + a JS content type so the browser
accepts a root scope.
"""

# ruff: noqa: PLC0415, S110
# Inline imports keep startup light; the defensive try/except/pass in
# _store_name is intentional — StoreSettings may not exist in dev.
from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_http_methods


def _config() -> dict:
    try:
        from plugins.models import PluginConfig

        cfg = PluginConfig.objects.filter(plugin_name='pwa').first()
        return (cfg.config or {}) if cfg else {}
    except Exception:  # noqa: BLE001
        return {}


def _store_name() -> str:
    """Store name from core.StoreSettings (foundational — not a plugin
    model), falling back to a sensible default."""
    try:
        from core.models import StoreSettings

        s = StoreSettings.objects.first()
        if s and getattr(s, 'store_name', ''):
            return s.store_name
    except Exception:  # noqa: BLE001
        pass
    return 'dot books'


def _theme_color() -> str:
    return (_config().get('theme_color') or '#f6f1e7').strip() or '#f6f1e7'


@require_http_methods(['GET'])
def manifest(request: HttpRequest) -> JsonResponse:
    """Web App Manifest. Served at /manifest.webmanifest with the
    correct content type so Chrome/Edge/Android treat the site as
    installable."""
    name = _store_name()
    resp = JsonResponse(
        {
            'name': name,
            'short_name': name[:12],
            'description': f'{name} — read, browse, and buy.',
            'start_url': '/?utm_source=pwa',
            'scope': '/',
            'display': 'standalone',
            'orientation': 'portrait',
            'theme_color': _theme_color(),
            'background_color': '#f6f1e7',
            'icons': [
                {
                    'src': static('pwa/icon-192.png'),
                    'sizes': '192x192',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': static('pwa/icon-512.png'),
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': static('pwa/icon-maskable-512.png'),
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'maskable',
                },
                {
                    'src': static('pwa/icon.svg'),
                    'sizes': 'any',
                    'type': 'image/svg+xml',
                    'purpose': 'any',
                },
            ],
        }
    )
    resp['Content-Type'] = 'application/manifest+json'
    resp['Cache-Control'] = 'public, max-age=3600'
    return resp


@require_http_methods(['GET'])
def service_worker(request: HttpRequest) -> HttpResponse:
    """The service worker script. Network-first for navigations (with
    an offline fallback), cache-first for static assets. Served from
    the root so its scope is the whole origin."""
    cfg = _config()
    offline_enabled = cfg.get('offline_enabled', True)
    # Bump CACHE version to invalidate old caches on deploy.
    js = _SW_TEMPLATE.replace('__OFFLINE_URL__', '/offline/' if offline_enabled else '')
    resp = HttpResponse(js, content_type='application/javascript; charset=utf-8')
    # Allow a root scope even though the file isn't physically at /.
    resp['Service-Worker-Allowed'] = '/'
    # Never let the SW itself be cached long — clients must pick up new
    # versions promptly.
    resp['Cache-Control'] = 'no-cache, max-age=0'
    return resp


@require_http_methods(['GET'])
def offline(request: HttpRequest) -> HttpResponse:
    """Branded offline fallback — shown by the SW when a navigation
    fails and nothing's cached."""
    return render(
        request,
        'pwa/offline.html',
        {
            'store_name': _store_name(),
        },
    )


@require_http_methods(['GET'])
def push_config(request: HttpRequest) -> JsonResponse:
    """Public VAPID public key for the client-side opt-in flow."""
    from django.conf import settings  # noqa: PLC0415

    vapid = (getattr(settings, 'PWA_PUSH', None) or {}).get('vapid_public_key', '')
    return JsonResponse({'vapid_public_key': vapid, 'enabled': bool(vapid)})


@require_http_methods(['POST'])
def push_subscribe(request: HttpRequest) -> JsonResponse:
    """Register/update a Web Push subscription from the storefront JS.

    Body shape (JSON):
      { endpoint, keys: {p256dh, auth}, topics?: ["cart_recovery", ...] }
    """
    from plugins.installed.pwa.models import PushSubscription  # noqa: PLC0415

    try:
        body = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

    endpoint = (body.get('endpoint') or '').strip()
    keys = body.get('keys') or {}
    p256dh = (keys.get('p256dh') or '').strip()
    auth = (keys.get('auth') or '').strip()
    topics = body.get('topics') or []
    if not (endpoint and p256dh and auth):
        return JsonResponse({'ok': False, 'error': 'missing_fields'}, status=400)

    user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    customer = request.user if request.user.is_authenticated else None
    visitor_id = request.COOKIES.get('morph_visitor', '')[:128]

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'customer': customer,
            'visitor_id': visitor_id,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': user_agent,
            'topics': topics if isinstance(topics, list) else [],
            'is_active': True,
        },
    )
    return JsonResponse({'ok': True})


@require_http_methods(['POST'])
def push_unsubscribe(request: HttpRequest) -> JsonResponse:
    """Deactivate a subscription by endpoint."""
    from plugins.installed.pwa.models import PushSubscription  # noqa: PLC0415

    try:
        body = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)
    endpoint = (body.get('endpoint') or '').strip()
    if not endpoint:
        return JsonResponse({'ok': False, 'error': 'missing_endpoint'}, status=400)
    PushSubscription.objects.filter(endpoint=endpoint).update(is_active=False)
    return JsonResponse({'ok': True})


# Service worker source. Kept as a Python string (not a static .js)
# so the offline URL can be toggled server-side + the cache version
# travels with deploys. Plain ES5-ish for maximum device support.
_SW_TEMPLATE = r"""
'use strict';
var CACHE = 'morph-pwa-v1';
var OFFLINE_URL = '__OFFLINE_URL__';
var PRECACHE = OFFLINE_URL ? [OFFLINE_URL] : [];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return PRECACHE.length ? cache.addAll(PRECACHE) : Promise.resolve();
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        if (k !== CACHE) return caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // Never cache auth, cart, checkout, account, admin, or API — these
  // must always hit the network (stale carts / sessions are dangerous).
  if (/^\/(auth|cart|checkout|account|dashboard|admin|api|mcp)\//.test(url.pathname)) {
    return;
  }

  // Navigations: network-first, fall back to cache, then offline page.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      }).catch(function () {
        return caches.match(req).then(function (hit) {
          return hit || (OFFLINE_URL ? caches.match(OFFLINE_URL) : Response.error());
        });
      })
    );
    return;
  }

  // Static assets (cache-first).
  if (/\.(css|js|woff2?|ttf|otf|png|jpe?g|webp|avif|gif|svg|ico)$/.test(url.pathname)
      || url.pathname.indexOf('/static/') === 0
      || url.pathname.indexOf('/media/') === 0) {
    event.respondWith(
      caches.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) {
          if (res && res.status === 200 && res.type === 'basic') {
            var copy = res.clone();
            caches.open(CACHE).then(function (c) { c.put(req, copy); });
          }
          return res;
        });
      })
    );
  }
});
"""
