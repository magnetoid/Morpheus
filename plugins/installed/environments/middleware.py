"""Resolve `request.environment` from the request — domain or X-Morph-Environment header."""

from __future__ import annotations

import logging

from django.db import DatabaseError

logger = logging.getLogger('morpheus.environments')


class EnvironmentMiddleware:
    """Attach an Environment instance to `request.environment` (or None if no match)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.environment = self._resolve(request)
        return self.get_response(request)

    @staticmethod
    def _resolve(request):
        from plugins.installed.environments.models import Environment

        slug = request.headers.get('X-Morph-Environment', '').strip()
        host = request.get_host().split(':')[0]
        try:
            if slug:
                return Environment.objects.filter(slug=slug, is_active=True).first()
            if host:
                env = Environment.objects.filter(domain=host, is_active=True).first()
                if env:
                    return env
            return Environment.objects.filter(kind='production', is_active=True).first()
        except DatabaseError as e:
            logger.warning('environments: resolve failed: %s', e)
            return None
