"""The background-agent scheduler tick is gated by the AUTONOMY_ENABLED filter.

Proactive runs are opt-in: with no subscriber enabling autonomy the tick fires
nothing, even for a due active agent; a subscriber returning True lets it run.
Manual `fire` is never gated (not covered here — it's an explicit human action).
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.agents.events import AgentEvents
from core.hooks import hook_registry
from plugins.installed.agent_core import scheduler
from plugins.installed.agent_core.models import BackgroundAgent


def _due_agent():
    return BackgroundAgent.objects.create(
        name='nightly',
        agent_name='worker',
        prompt='do the thing',
        interval_seconds=3600,
        state=BackgroundAgent.STATE_ACTIVE,
        next_run_at=timezone.now() - timezone.timedelta(seconds=10),
    )


class TickAutonomyGateTests(TestCase):
    def test_tick_does_not_fire_when_autonomy_disabled(self):
        _due_agent()
        # No AUTONOMY_ENABLED subscriber returns True → filter stays False.
        with patch.object(scheduler, 'fire') as fire:
            fired = scheduler.tick()
        self.assertEqual(fired, 0)
        fire.assert_not_called()

    def test_tick_fires_due_agent_when_autonomy_enabled(self):
        _due_agent()
        handler = lambda value, **_: True  # noqa: E731 — temp gate-opener
        hook_registry.register(AgentEvents.AUTONOMY_ENABLED, handler, priority=1)
        try:
            with patch.object(scheduler, 'fire', return_value={'ok': True}) as fire:
                fired = scheduler.tick()
        finally:
            hook_registry.unregister(AgentEvents.AUTONOMY_ENABLED, handler)
        self.assertEqual(fired, 1)
        fire.assert_called_once()
