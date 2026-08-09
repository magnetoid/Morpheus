"""Trusted Agent middleware — reads Cloudflare's verification headers.

When Cloudflare verifies a signed agent request (Visa Trusted Agent
Protocol or Mastercard Verifiable Intent), it stamps the request with
``X-Verified-Agent-*`` headers before proxying to origin. This
middleware reads those headers and attaches a ``request.trusted_agent``
namespace so downstream views (and the checkout flow specifically)
can persist the agent ID onto the resulting order.

**Origin lock (security).** ``X-Verified-Agent-*`` are ordinary request
headers — a client that reaches origin directly (past the
CF→Plesk→Traefik→web chain) could set them and spoof the agent id stamped
onto orders. So the headers are trusted **only** when the request also
carries a shared secret that Cloudflare injects on proxied requests:
``X-Verified-Agent-Origin-Secret`` must equal ``settings.TRUSTED_AGENT_PROXY_SECRET``.
When that secret is unset (default), the headers are NOT trusted and
``request.trusted_agent`` is None — fail-closed. To enable trusted-agent
stamping: set ``TRUSTED_AGENT_PROXY_SECRET`` in the origin env AND configure
Cloudflare (Transform Rule / Worker) to add the matching header on proxied
traffic. A direct-to-origin client can't supply the secret, so its spoofed
agent headers are ignored.

Gating an endpoint on a verified agent is still the view's responsibility;
this middleware only attaches (or withholds) the namespace.
"""

from __future__ import annotations

import hmac
import logging
import threading
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger('morpheus.agent_mcp.trusted_agent')

# One-shot "headers ignored" warning guard — a list so we mutate (not rebind)
# and avoid a `global` statement.
_warned_untrusted: list = []


def _origin_verified(request) -> bool:
    """True only when the request carries the Cloudflare-injected shared secret,
    proving the ``X-Verified-Agent-*`` headers came through our proxy and were
    not spoofed by a direct-to-origin client. Fail-closed when unconfigured."""
    secret = (getattr(settings, 'TRUSTED_AGENT_PROXY_SECRET', '') or '').strip()
    if not secret:
        return False
    presented = request.META.get('HTTP_X_VERIFIED_AGENT_ORIGIN_SECRET', '')
    return bool(presented) and hmac.compare_digest(presented, secret)


# The verified agent for the in-flight request. Set by the middleware and read
# by the ORDER_PLACED hook handler (which only receives `order`, not `request`).
_current = threading.local()


def current_trusted_agent():
    """The TrustedAgent for the in-flight request, or None."""
    return getattr(_current, 'agent', None)


@dataclass
class TrustedAgent:
    agent_id: str
    provider: str  # 'visa' / 'mastercard' / 'cloudflare'
    signature: str = ''


class TrustedAgentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        agent_id = request.META.get('HTTP_X_VERIFIED_AGENT_ID', '').strip()
        if agent_id and _origin_verified(request):
            request.trusted_agent = TrustedAgent(
                agent_id=agent_id[:120],
                provider=request.META.get(
                    'HTTP_X_VERIFIED_AGENT_PROVIDER',
                    'cloudflare',
                )[:32],
                signature=request.META.get(
                    'HTTP_X_VERIFIED_AGENT_SIGNATURE',
                    '',
                )[:300],
            )
        else:
            if agent_id and not _warned_untrusted:
                # Headers present but origin unverified — ignored (fail-closed).
                # Logged once so a misconfigured proxy secret is diagnosable.
                _warned_untrusted.append(1)
                logger.warning(
                    'trusted-agent: X-Verified-Agent-* headers present but origin '
                    'not verified (TRUSTED_AGENT_PROXY_SECRET unset or header '
                    'mismatch); ignoring the agent claim.'
                )
            request.trusted_agent = None
        _current.agent = request.trusted_agent
        try:
            return self.get_response(request)
        finally:
            _current.agent = None


def stamp_order_with_agent(order, agent=None) -> bool:
    """Persist the verified agent id onto an order's metadata. Idempotent;
    no-op (returns False) when no trusted agent was present on the request.
    `agent` defaults to the in-flight request's TrustedAgent (thread-local),
    so the ORDER_PLACED hook handler can call it with just the order."""
    agent = agent or current_trusted_agent()
    if agent is None:
        return False
    try:
        meta = order.metadata or {}
        meta['agent_id'] = agent.agent_id
        meta['agent_provider'] = agent.provider
        order.metadata = meta
        order.save(update_fields=['metadata', 'updated_at'])
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning('trusted-agent order stamp failed for %s: %s', getattr(order, 'id', '?'), e)
        return False
