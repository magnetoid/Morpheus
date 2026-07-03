"""Linda's daily briefing — a proactive, read-only Worker run.

Once a day (beat: 06:00 UTC) a Worker with a read-only scope set reviews the
last 24 hours — orders/revenue, new errors, low stock, anything its read
tools reveal — and produces a short narrative plus up to 3 delegable actions.
Actions are NEVER executed here: each renders on the dashboard home as an
"Ask Linda" link that prefills the chat, so every write still goes through
Linda's existing confirmed-write gates.

Master switch: Settings → General → *Linda's daily briefing*
(``StoreSettings.ai_daily_briefing``, default off).

Overlap note: distinct from Linda's Pulse (rule-based alert cards owned by
the ai_assistant plugin) — this is an open-ended agentic review. See
docs/plans/linda-self-learning-2026-07.md.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger('morpheus.assistant.briefing')

_SKIP_PROVIDERS = ('mock', 'unconfigured')
_MAX_ACTIONS = 3

_OBJECTIVE = (
    "Write the merchant's MORNING BRIEFING for the last 24 hours.\n"
    'Use only read tools — gather what actually happened: orders and revenue '
    '(vs the day before if available), notable errors in the platform logs, '
    'low or out-of-stock products, new reviews, and anything else your tools '
    'surface that a store owner should know before coffee. If the '
    'analytics.ai_traffic tool is available, include an AI-visibility note '
    'when there is anything to say (sessions/revenue referred by ChatGPT/'
    'Perplexity/etc., AI crawlers reading the catalog). Never invent '
    'numbers — cite tools.\n\n'
    'Then reply with ONLY this JSON object, no prose around it:\n'
    '{"briefing": "4-8 short lines, one finding per line, plain text, '
    'most important first — warm but concrete",\n'
    ' "actions": [{"label": "3-6 word button label", '
    '"prompt": "the exact request the merchant would send Linda to act on it"}]}\n'
    f'At most {_MAX_ACTIONS} actions; only actions genuinely worth doing today. '
    'An empty actions list is fine on a quiet day.'
)


def latest_briefing(*, max_age_days: int = 2) -> dict[str, Any] | None:
    """The most recent OK briefing for the home panel, or None (feature off,
    nothing generated yet, or the newest briefing is stale). Fail-soft."""
    try:
        from django.utils import timezone

        from core.assistant.models import AssistantBriefing
        from core.models import StoreSettings

        if not StoreSettings.get('ai_daily_briefing', False):
            return None
        row = AssistantBriefing.objects.filter(status='ok').order_by('-date').first()
        if row is None or (timezone.localdate() - row.date).days > max_age_days:
            return None
        actions = [
            a
            for a in (row.actions or [])
            if isinstance(a, dict) and a.get('label') and a.get('prompt')
        ]
        return {'date': row.date, 'body': row.body, 'actions': actions[:_MAX_ACTIONS]}
    except Exception:  # noqa: BLE001 — the home page must never break over this
        logger.debug('briefing: latest_briefing failed', exc_info=True)
        return None


def _read_only_worker():
    """A fresh Worker whose scope set keeps only ``*.read`` scopes, so the
    runtime's policy layer hides every write tool from the briefing run."""
    from core.agents import agent_registry

    agent = agent_registry.get_agent('worker')
    if agent is None:
        raise RuntimeError('worker agent not registered')
    clone = type(agent)()
    clone.scopes = [s for s in agent.scopes if s.endswith('.read')]
    return clone


def run_daily_briefing(*, provider=None, force: bool = False) -> dict[str, Any]:
    """Generate today's briefing. Returns a small status dict; never raises.

    Idempotent per day (`force=True` regenerates). Skips without writing a
    row when the feature is off or no provider is configured — a `failed`
    row is only stored for a real attempt that broke, so the beat task
    can't crash-loop rows into the table.
    """
    try:
        from django.utils import timezone

        from core.assistant.models import AssistantBriefing
        from core.models import StoreSettings

        if not StoreSettings.get('ai_daily_briefing', False):
            return {'skipped': 'disabled'}
        today = timezone.localdate()
        if not force and AssistantBriefing.objects.filter(date=today).exists():
            return {'skipped': 'already generated today'}
        if provider is None:
            from core.assistant.providers import get_default_provider

            provider = get_default_provider()
            if getattr(provider, 'name', '') in _SKIP_PROVIDERS:
                return {'skipped': 'no provider configured'}

        from core.agents import AgentRuntime
        from core.llm_parsing import parse_llm_json

        started = time.monotonic()
        runtime = AgentRuntime(_read_only_worker(), provider=provider)
        result = runtime.run(user_message=_OBJECTIVE, history=[], context={'briefing': True})
        duration_ms = int((time.monotonic() - started) * 1000)

        parsed = parse_llm_json(result.text or '')
        body = ''
        actions: list[dict] = []
        if isinstance(parsed, dict):
            body = str(parsed.get('briefing') or '').strip()
            actions = [
                {'label': str(a.get('label'))[:60], 'prompt': str(a.get('prompt'))[:500]}
                for a in (parsed.get('actions') or [])[:_MAX_ACTIONS]
                if isinstance(a, dict) and a.get('label') and a.get('prompt')
            ]
        if not body:
            # Model ignored the JSON contract — keep the raw text rather
            # than losing the (tool-grounded) review.
            body = (result.text or '').strip()

        ok = result.state == 'completed' and bool(body)
        row, _ = AssistantBriefing.objects.update_or_create(
            date=today,
            defaults={
                'status': 'ok' if ok else 'failed',
                'body': body[:10_000],
                'actions': actions,
                'error': (result.error or ('' if ok else 'empty briefing'))[:500],
                'provider': getattr(provider, 'name', '')[:40],
                'model': (getattr(provider, 'model', '') or '')[:100],
                'duration_ms': duration_ms,
            },
        )
        logger.info(
            'briefing: date=%s status=%s actions=%d duration=%dms',
            today,
            row.status,
            len(actions),
            duration_ms,
        )
        return {'status': row.status, 'date': str(today), 'actions': len(actions)}
    except Exception as e:  # noqa: BLE001 — beat task must never crash-loop
        logger.warning('briefing: failed: %s', e, exc_info=True)
        return {'skipped': str(e)[:200]}
