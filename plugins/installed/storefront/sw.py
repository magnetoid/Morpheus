"""Service Worker — served at /sw.js when the Caching page toggle is on.

Strategy:
  - HTML pages → network-first with a 3s timeout, fall back to cache,
    fall back to the offline page.
  - Static assets (/static/, /media/) → cache-first with background
    revalidate. Long Cache-Control max-age already handles browser
    HTTP cache; this layer adds offline support.

The worker version is the deploy SHA when available, so each Coolify
deploy installs a fresh worker instead of riding the old one.
"""

from __future__ import annotations

import os

from django.http import HttpResponse


def _worker_version() -> str:
    return os.environ.get('GIT_COMMIT_SHA', os.environ.get('COOLIFY_BUILD_HASH', 'dev'))[:12]


def service_worker_js(request) -> HttpResponse:
    """Render /sw.js. Only served when the merchant has enabled the
    PWA toggle on the Caching settings page — otherwise the registration
    script at the top of base.html doesn't run, so this URL never gets
    hit anyway. Worth refusing here too for direct hits."""
    from plugins.registry import plugin_registry

    p = plugin_registry.get('storefront')
    cfg = (p.get_config() if p else {}) or {}
    if not cfg.get('service_worker_enabled'):
        return HttpResponse('', status=404, content_type='application/javascript')

    version = _worker_version()
    offline_path = (cfg.get('offline_page_path') or '/offline/').strip()
    js = (
        f'const VERSION = {version!r};\n'
        f'const OFFLINE_PATH = {offline_path!r};\n'
        f'const STATIC_CACHE = `morpheus-static-${{VERSION}}`;\n'
        f'const HTML_CACHE = `morpheus-html-${{VERSION}}`;\n'
        '\n'
        "self.addEventListener('install', e => {\n"
        '  e.waitUntil(\n'
        "    caches.open(HTML_CACHE).then(c => c.add(new Request(OFFLINE_PATH, {cache: 'reload'})))\n"
        '      .then(() => self.skipWaiting())\n'
        '  );\n'
        '});\n'
        '\n'
        "self.addEventListener('activate', e => {\n"
        '  e.waitUntil((async () => {\n'
        '    const names = await caches.keys();\n'
        '    await Promise.all(\n'
        '      names.filter(n => !n.endsWith(VERSION)).map(n => caches.delete(n))\n'
        '    );\n'
        '    await self.clients.claim();\n'
        '  })());\n'
        '});\n'
        '\n'
        "self.addEventListener('fetch', e => {\n"
        '  const req = e.request;\n'
        "  if (req.method !== 'GET') return;\n"
        '  const url = new URL(req.url);\n'
        '  if (url.origin !== self.location.origin) return;\n'
        '\n'
        '  // Static assets — cache-first w/ background revalidate.\n'
        "  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {\n"
        '    e.respondWith((async () => {\n'
        '      const cache = await caches.open(STATIC_CACHE);\n'
        '      const cached = await cache.match(req);\n'
        '      const fetched = fetch(req).then(r => {\n'
        '        if (r.ok) cache.put(req, r.clone());\n'
        '        return r;\n'
        '      }).catch(() => null);\n'
        "      return cached || fetched || new Response('', {status: 504});\n"
        '    })());\n'
        '    return;\n'
        '  }\n'
        '\n'
        '  // HTML pages — network-first with 3s timeout, cache fallback,\n'
        '  // offline-page fallback.\n'
        "  const accept = req.headers.get('Accept') || '';\n"
        "  if (req.mode === 'navigate' || accept.includes('text/html')) {\n"
        '    e.respondWith((async () => {\n'
        '      const cache = await caches.open(HTML_CACHE);\n'
        '      try {\n'
        '        const fetched = await Promise.race([\n'
        '          fetch(req),\n'
        "          new Promise((_, rj) => setTimeout(() => rj(new Error('timeout')), 3000)),\n"
        '        ]);\n'
        '        if (fetched && fetched.ok) cache.put(req, fetched.clone());\n'
        '        return fetched;\n'
        '      } catch (_) {\n'
        '        const cached = await cache.match(req);\n'
        '        if (cached) return cached;\n'
        "        return (await cache.match(OFFLINE_PATH)) || new Response('Offline', {status: 503});\n"
        '      }\n'
        '    })());\n'
        '  }\n'
        '});\n'
    )
    response = HttpResponse(js, content_type='application/javascript')
    # Workers MUST not be cached aggressively or new deploys ride
    # the old worker for hours. 5 min lets CDN edges hold briefly.
    response['Cache-Control'] = 'public, max-age=300, must-revalidate'
    response['Service-Worker-Allowed'] = '/'
    return response


def offline_page(request) -> HttpResponse:
    """Minimal offline fallback rendered when the worker can't reach the network."""
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>Offline</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>body{font-family:system-ui,sans-serif;max-width:480px;margin:6rem auto;'
        'padding:2rem;color:#1a1a1a;text-align:center}h1{margin:0 0 .5rem;font-size:1.25rem}'
        'p{color:#6b7280;margin:0 0 1.5rem}'
        'button{padding:.6rem 1.2rem;border:1px solid #1a1a1a;background:#fff;'
        'border-radius:6px;font:inherit;cursor:pointer}</style>'
        '<h1>You are offline</h1>'
        "<p>This page isn't saved for offline use. Reconnect and try again.</p>"
        '<button onclick="location.reload()">Retry</button>'
    )
    response = HttpResponse(html, content_type='text/html')
    response['Cache-Control'] = 'public, max-age=86400'
    return response
