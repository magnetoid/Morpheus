"""PUBLIC, cross-origin embeddable-widget endpoints.

Three anonymous endpoints, each addressed by an unguessable widget ``key``:

  embed_iframe   GET /affiliates/embed/<key>/          → self-contained themed
                 HTML grid, framable on ANY external site (per-response
                 framing relaxation, scoped to this view only).
  widget_json    GET /api/affiliates/widget/<key>.json → CORS JSON, public
                 product data + ref links only.
  embed_js       GET /affiliates/embed/<key>.js        → CORS JS that fetches
                 the JSON and injects XSS-safe cards into a target <div>.

SECURITY (these are the only intentionally cross-origin-readable surfaces in
the plugin — review them as such):
  * No auth, by design. Access is gated by the 24-byte ``key`` + ``is_active``.
  * Output is whitelisted public product data only — see ``widgets.serialize_*``.
    No customer / order / cost / PII fields ever cross the boundary.
  * Framing relaxation is PER-RESPONSE on the iframe view only
    (``@xframe_options_exempt`` drops the site-wide ``X-Frame-Options: DENY``;
    a per-response CSP sets ``frame-ancestors *`` and pre-empts the site-wide
    report-only ``frame-ancestors 'none'``). The rest of the site is untouched.
  * CORS (``Access-Control-Allow-Origin: *``) is set ONLY on the JSON + JS
    responses. The iframe HTML does NOT get CORS — it's loaded as a document,
    not fetched.
  * Results are bounded (``widget.effective_limit`` ≤ 24) and the responses
    carry a short ``Cache-Control`` so a CDN/edge can absorb load.
  * XSS-safe rendering: the iframe template uses Django auto-escaping (no
    ``|safe`` on product fields); the JS builds nodes with ``textContent`` and
    sets ``img.src`` / ``a.href`` only after an http(s) scheme check —
    ``innerHTML`` is never fed product data.
"""

# ruff: noqa: PLC0415  — inline imports match the plugin's house style.
from __future__ import annotations

import json

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_http_methods

# A permissive CSP scoped to a single response. `frame-ancestors *` lets the
# page be framed anywhere; setting it here also stops SecurityHeadersMiddleware
# from layering its site-wide report-only `frame-ancestors 'none'` on top (the
# middleware only injects when these header names are absent).
_EMBED_CSP = "frame-ancestors *; default-src 'self' data: https:; img-src 'self' data: https:"
_CACHE = 'public, max-age=300'


def _get_active_widget(key: str):
    """Resolve an active widget by its public key, or 404.

    Validates the key shape first (token_urlsafe alphabet, bounded length) so a
    junk path can't reach the DB lookup. 404 — never reveal whether a key
    exists-but-inactive vs never-existed.
    """
    from plugins.installed.affiliates.models import AffiliateWidget

    if not key or len(key) > 64 or not all(c.isalnum() or c in '-_' for c in key):
        raise Http404('widget not found')
    widget = (
        AffiliateWidget.objects.select_related('affiliate', 'link')
        .filter(key=key, is_active=True)
        .first()
    )
    if widget is None:
        raise Http404('widget not found')
    return widget


def _site_base(request) -> str:
    return request.build_absolute_uri('/').rstrip('/')


@xframe_options_exempt
@require_http_methods(['GET'])
def embed_iframe(request, key: str) -> HttpResponse:
    """Self-contained, framable themed product grid for ``<iframe>`` embeds."""
    from plugins.installed.affiliates.widgets import serialize_widget

    widget = _get_active_widget(key)
    payload = serialize_widget(widget, base=_site_base(request))

    response = render(
        request,
        'affiliates/embed/widget.html',
        {
            'title': payload['title'],
            'theme': payload['theme'] if payload['theme'] in ('light', 'dark', 'auto') else 'auto',
            'layout': payload['layout'] if payload['layout'] in ('grid', 'carousel') else 'grid',
            'products': payload['products'],
            'store_url': _site_base(request),
        },
    )
    # Per-response framing relaxation — THIS endpoint only. @xframe_options_exempt
    # already suppressed the site-wide X-Frame-Options: DENY; the CSP below both
    # whitelists all ancestors and blocks the middleware's report-only default.
    response['Content-Security-Policy'] = _EMBED_CSP
    # Pre-empt SecurityHeadersMiddleware (it sets this header name only if absent
    # on non-dashboard paths) so the storefront's `frame-ancestors 'none'`
    # report-only policy never lands on the embed.
    response['Content-Security-Policy-Report-Only'] = _EMBED_CSP
    response['Cache-Control'] = _CACHE
    return response


def _cors_json(payload: dict, *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status)
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Cache-Control'] = _CACHE
    return response


@require_http_methods(['GET', 'OPTIONS'])
def widget_json(request, key: str) -> JsonResponse:
    """CORS-enabled public JSON: widget meta + public product cards.

    Consumed cross-origin by the JS snippet. Public product data only.
    """
    if request.method == 'OPTIONS':
        return _cors_json({}, status=204)

    from plugins.installed.affiliates.widgets import serialize_widget

    widget = _get_active_widget(key)
    payload = serialize_widget(widget, base=_site_base(request))
    return _cors_json(payload)


@require_http_methods(['GET'])
def embed_js(request, key: str) -> HttpResponse:
    """CORS-enabled JS snippet. Dropped on an external page via

        <script src="https://store/affiliates/embed/<key>.js"
                data-target="morph-aff-<key>"></script>
        <div id="morph-aff-<key>"></div>

    The script fetches the JSON endpoint and injects XSS-safe cards into the
    target div. Product strings are written via ``textContent``; ``img.src`` /
    ``a.href`` are assigned only after an http(s) scheme check. ``innerHTML``
    is never given product data.
    """
    # 404 early on a bad/inactive key so the snippet doesn't ship for nothing.
    _get_active_widget(key)

    base = _site_base(request)
    json_url = f'{base}/api/affiliates/widget/{key}.json'
    target_id = f'morph-aff-{key}'
    # json.dumps gives us safely-quoted JS string literals for the two values
    # we interpolate into the script body (no user-controlled data here — key
    # is validated alnum/-/_, base is our own host — but we quote defensively).
    # str.replace (not %-formatting) because the snippet's inline CSS contains
    # literal '%' (e.g. width:100%) that would break %-interpolation.
    js = _SNIPPET_TEMPLATE.replace('__JSON_URL__', json.dumps(json_url)).replace(
        '__TARGET_ID__', json.dumps(target_id)
    )
    response = HttpResponse(js, content_type='application/javascript; charset=utf-8')
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = _CACHE
    return response


# The injected snippet. XSS-safe by construction: every product string goes
# through document.createTextNode / textContent; image + link URLs are
# assigned only after a scheme check; nothing is ever set via innerHTML.
_SNIPPET_TEMPLATE = r"""(function () {
  var JSON_URL = __JSON_URL__;
  var TARGET_ID = __TARGET_ID__;
  // Capture the script element NOW — document.currentScript is only valid
  // during synchronous execution, not inside the deferred boot() callback.
  var THIS_SCRIPT = document.currentScript;

  function safeUrl(u) {
    if (typeof u !== 'string') return '';
    return (/^https?:\/\//i.test(u) || u.charAt(0) === '/') ? u : '';
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = String(text);
    return e;
  }

  function card(p) {
    var a = el('a', 'morph-aff-card');
    var href = safeUrl(p && p.url);
    if (href) { a.setAttribute('href', href); a.setAttribute('target', '_blank'); a.setAttribute('rel', 'nofollow noopener sponsored'); }
    var imgUrl = safeUrl(p && p.image);
    if (imgUrl) {
      var img = el('img', 'morph-aff-card__img');
      img.setAttribute('src', imgUrl);
      img.setAttribute('alt', (p && p.name) ? String(p.name) : '');
      img.setAttribute('loading', 'lazy');
      a.appendChild(img);
    }
    a.appendChild(el('div', 'morph-aff-card__title', (p && p.name) || ''));
    var price = el('div', 'morph-aff-card__price', (p && p.price) || '');
    if (p && p.on_sale && p.compare_at_price) {
      price.appendChild(el('span', 'morph-aff-card__compare', p.compare_at_price));
    }
    a.appendChild(price);
    return a;
  }

  function render(data, mount) {
    mount.textContent = '';
    var wrap = el('div', 'morph-aff-widget morph-aff-widget--' + ((data && data.theme) || 'auto'));
    if (data && data.title) wrap.appendChild(el('div', 'morph-aff-widget__title', data.title));
    var grid = el('div', 'morph-aff-grid');
    var products = (data && data.products) || [];
    for (var i = 0; i < products.length; i++) grid.appendChild(card(products[i]));
    wrap.appendChild(grid);
    mount.appendChild(wrap);
  }

  function injectStyles() {
    if (document.getElementById('morph-aff-styles')) return;
    var css = ".morph-aff-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:14px}"
      + ".morph-aff-card{display:block;text-decoration:none;color:inherit;border:1px solid rgba(0,0,0,.08);border-radius:10px;overflow:hidden;background:#fff;transition:box-shadow .15s}"
      + ".morph-aff-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.1)}"
      + ".morph-aff-card__img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;background:#f3f3f3}"
      + ".morph-aff-card__title{font:600 13px/1.3 system-ui,sans-serif;padding:8px 10px 2px}"
      + ".morph-aff-card__price{font:600 13px/1.3 system-ui,sans-serif;padding:0 10px 10px}"
      + ".morph-aff-card__compare{color:#999;text-decoration:line-through;font-weight:400;margin-left:6px}"
      + ".morph-aff-widget__title{font:700 16px/1.3 system-ui,sans-serif;margin:0 0 12px}"
      + ".morph-aff-widget--dark .morph-aff-card{background:#1a1a1a;border-color:rgba(255,255,255,.12);color:#eee}"
      + ".morph-aff-widget--dark .morph-aff-card__img{background:#222}";
    var s = document.createElement('style');
    s.id = 'morph-aff-styles';
    s.appendChild(document.createTextNode(css));
    document.head.appendChild(s);
  }

  function boot() {
    var script = THIS_SCRIPT;
    var mount = document.getElementById(TARGET_ID)
      || (script && script.getAttribute('data-target') && document.getElementById(script.getAttribute('data-target')));
    if (!mount) { mount = el('div'); if (script && script.parentNode) script.parentNode.insertBefore(mount, script); }
    injectStyles();
    fetch(JSON_URL, { credentials: 'omit' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) render(data, mount); })
      .catch(function () {});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
"""
