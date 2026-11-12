"""Auto-track storefront pageviews. Cheap, never blocks the response."""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.analytics')

# Paths that should NOT generate pageview events. Admin, API, healthchecks,
# webhooks, static, etc.
_EXCLUDED_PREFIXES = (
    '/admin/',
    '/api/',
    '/graphql',
    '/healthz',
    '/static/',
    '/media/',
    '/dashboard/',
    '/auth/',
)


def _hit_tag(request) -> bytes:
    from django.templatetags.static import static
    from django.utils.html import escape

    # A payment page runs only scripts that carry its nonce (core/security_headers.py).
    nonce = str(getattr(request, 'csp_nonce', '') or '')
    attr = f' nonce="{escape(nonce)}"' if nonce else ''
    src = escape(static('analytics/hit.js'))
    return f'<script src="{src}" defer data-morph-hit{attr}></script>'.encode()


def _add_hit(request, response) -> None:
    """Put the page's own pageview script before ``</body>``.

    The browser counts the page, so a copy Cloudflare serves from its cache is
    counted as well (the server never sees those), each page load once, and
    a page that answers a redirect or an error gets no script at all.
    """
    if response.streaming or response.status_code != 200:
        return
    content = response.content
    at = content.rfind(b'</body>')
    if at == -1 or b'data-morph-hit' in content:
        return
    response.content = content[:at] + _hit_tag(request) + content[at:]
    if response.has_header('Content-Length'):
        response['Content-Length'] = str(len(response.content))


class AnalyticsMiddleware:
    """Sets the visitor's analytics cookie and adds the pageview script to
    storefront pages; the script's hit is the pageview."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or ''
        if request.method != 'GET' or path.startswith(_EXCLUDED_PREFIXES):
            return response
        try:
            from plugins.installed.analytics.services import (
                ai_crawler_from_ua,
                get_or_create_session,
                record_ai_crawler_hit,
                should_track_request,
            )

            # AI crawlers (GPTBot, ClaudeBot, PerplexityBot, ...) are counted
            # as catalog reads — the merchant's "AI is reading my store"
            # signal — and are NOT visitor sessions/pageviews.
            ua = request.META.get('HTTP_USER_AGENT', '')
            bot = ai_crawler_from_ua(ua)
            if bot:
                record_ai_crawler_hit(bot)
                return response
            # Every other crawler (search engines, SEO tools, previews) is not
            # a visitor either.
            from core.utils.crawlers import is_crawler_user_agent  # noqa: PLC0415

            if is_crawler_user_agent(ua):
                return response
            # A pageview is a page: a script's JSON fetch is not one.
            if not (response.get('Content-Type') or '').startswith('text/html'):
                return response

            if not should_track_request(request):
                return response  # staff/admin browsing — don't pollute analytics
            if response.status_code == 200:
                # The visitor's session starts on the page, with its referrer.
                get_or_create_session(request, response=response)
            _add_hit(request, response)
        except Exception as e:  # noqa: BLE001 — never break a response
            logger.debug('analytics: page handling failed: %s', e)
        return response
