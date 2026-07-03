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


class AnalyticsMiddleware:
    """Sets the analytics cookie + records a pageview on storefront GETs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method != 'GET':
            return response
        path = request.path or ''
        if path.startswith(_EXCLUDED_PREFIXES):
            return response
        try:
            from plugins.installed.analytics.services import (
                ai_crawler_from_ua,
                get_or_create_session,
                record_ai_crawler_hit,
                record_event,
                should_track_request,
            )

            # AI crawlers (GPTBot, ClaudeBot, PerplexityBot, ...) are counted
            # as catalog reads — the merchant's "AI is reading my store"
            # signal — and are NOT visitor sessions/pageviews (they used to
            # pollute both).
            bot = ai_crawler_from_ua(request.META.get('HTTP_USER_AGENT', ''))
            if bot:
                record_ai_crawler_hit(bot)
                return response

            if not should_track_request(request):
                return response  # staff/admin browsing — don't pollute analytics
            session = get_or_create_session(request, response=response)
            record_event(
                name='pageview',
                kind='pageview',
                session=session,
                request=request,
                url=path[:500],
            )
        except Exception as e:  # noqa: BLE001 — never break a response
            logger.debug('analytics: pageview record failed: %s', e)
        return response
