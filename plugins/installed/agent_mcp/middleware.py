"""Trusted Agent middleware — reads Cloudflare's verification headers.

When Cloudflare verifies a signed agent request (Visa Trusted Agent
Protocol or Mastercard Verifiable Intent), it stamps the request with
``X-Verified-Agent-*`` headers before proxying to origin. This
middleware reads those headers and attaches a ``request.trusted_agent``
namespace so downstream views (and the checkout flow specifically)
can persist the agent ID onto the resulting order.

If no verification headers are present, ``request.trusted_agent`` is
None — the request flows through unchanged. There is no enforcement
here: gating an endpoint on a verified agent is the responsibility of
the view, not the middleware.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger('morpheus.agent_mcp.trusted_agent')

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
        if agent_id:
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
