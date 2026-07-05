"""Per-product agent-checkout eligibility.

A product carrying the metafield ``agentic.exclude`` (namespace ``agentic``,
key ``exclude``, truthy) is excluded from agent checkout: rejected at
session create/update with an item-scoped ``MessageError`` and flagged
``is_eligible_checkout: false`` in the ACP feed. Fail-soft: metafields
disabled/absent → everything is eligible.
"""

from __future__ import annotations


def agentic_excluded(product) -> bool:
    """``True`` when the product opted out of agent checkout."""
    try:
        from plugins.installed.metafields.models import Metafield

        return bool(Metafield.objects.for_obj(product, ns='agentic').get('agentic.exclude'))
    except Exception:  # noqa: BLE001 — metafields absent/disabled → eligible
        return False
