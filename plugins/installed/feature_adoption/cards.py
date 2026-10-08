"""The feature-adoption card on the Analytics overview (DashboardCard)."""

from __future__ import annotations


def adoption_card(request) -> dict:
    """The install-health score and its three parts."""
    from plugins.installed.feature_adoption.tracking import (
        AGENT_PTS,
        BREADTH_PTS,
        FRESH_PTS,
        install_health,
    )

    health = install_health()
    parts = health.get('components') or {}
    score = health.get('score', 0)
    return {
        'value': f'{score}/100',
        'caption': 'install health — which apps get used',
        'tone': 'ok' if score >= 70 else ('warn' if score < 40 else ''),
        'rows': [
            ('Apps in use', f'{parts.get("breadth", 0)}/{BREADTH_PTS}'),
            ('Linda tool calls', f'{parts.get("agent", 0)}/{AGENT_PTS}'),
            ('Recent dashboard use', f'{parts.get("freshness", 0)}/{FRESH_PTS}'),
        ],
    }
