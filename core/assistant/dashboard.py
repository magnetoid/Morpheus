"""Dashboard-home contributions (ACTIVITY_FEED filter) — pending OpsProposals.

Registered from ``AssistantConfig.ready()`` (core-owned handler, never gated
by a plugin toggle — the assistant layer is core). One feed item when at
least one 'proposed' OpsProposal awaits review; fail-soft when the table
isn't migrated yet (fresh boot).
"""

from __future__ import annotations


def on_activity_feed(value, limit=20, **kwargs):
    """Append a single 'staged changes awaiting review' item to the feed."""
    from core.assistant.models import OpsProposal  # noqa: PLC0415

    try:
        pending = OpsProposal.objects.filter(status='proposed')
        newest = pending.first()  # Meta.ordering = ['-created_at']
        if newest is None:
            return value
        n = pending.count()
    except Exception:  # noqa: BLE001 — table missing pre-migrate; feed is best-effort
        return value
    value.append(
        {
            'kind': 'ops_proposal',
            'icon': 'inbox',
            'label': f'{n} staged change(s) awaiting review',
            'hint': newest.title,
            'url': '/dashboard/assistant/proposals/',
            'when': newest.created_at,
        }
    )
    return value
