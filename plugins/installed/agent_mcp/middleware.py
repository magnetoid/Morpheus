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

from dataclasses import dataclass


@dataclass
class TrustedAgent:
    agent_id: str
    provider: str       # 'visa' / 'mastercard' / 'cloudflare'
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
                    'HTTP_X_VERIFIED_AGENT_PROVIDER', 'cloudflare',
                )[:32],
                signature=request.META.get(
                    'HTTP_X_VERIFIED_AGENT_SIGNATURE', '',
                )[:300],
            )
        else:
            request.trusted_agent = None
        return self.get_response(request)


def stamp_order_with_agent(order, request) -> None:
    """Persist the verified agent id onto an order's metadata. Called
    from the checkout completion path. Idempotent; no-op when no
    trusted agent header was present."""
    agent = getattr(request, 'trusted_agent', None)
    if agent is None:
        return
    try:
        meta = order.metadata or {}
        meta['agent_id'] = agent.agent_id
        meta['agent_provider'] = agent.provider
        order.metadata = meta
        order.save(update_fields=['metadata', 'updated_at'])
    except Exception:  # noqa: BLE001 — never block checkout on bookkeeping
        pass
