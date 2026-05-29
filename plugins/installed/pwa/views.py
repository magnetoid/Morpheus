"""PWA endpoints: manifest, service worker, offline fallback.

All three are public + cacheable. The service worker is served with
``Service-Worker-Allowed: /`` + a JS content type so the browser
accepts a root scope.
"""
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
    resp = JsonResponse({
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
            {'src': static('pwa/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('pwa/icon-maskable-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
            {'src': static('pwa/icon.svg'), 'sizes': 'any', 'type': 'image/svg+xml', 'purpose': 'any'},
        ],
    })
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
    return render(request, 'pwa/offline.html', {
        'store_name': _store_name(),
    })


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
