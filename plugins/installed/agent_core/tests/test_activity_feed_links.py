"""The Home activity feed links an agent run to a page that exists.

It linked `/dashboard/agents/runs/<id>/`, which no route serves — the run
detail lives at `/dashboard/agents/<id>/` — so every agent row on Home 404'd.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import resolve


class ActivityFeedLinkTests(TestCase):
    def test_an_agent_run_links_to_its_detail_page(self):
        from plugins.installed.agent_core.models import AgentRun
        from plugins.registry import app_registry

        run = AgentRun.objects.create(agent_name='worker', user_message='check stock')
        items = app_registry.get('agent_core').on_activity_feed([], limit=5)
        url = next(i['url'] for i in items if i['kind'] == 'agent')
        self.assertEqual(resolve(url).url_name, 'run_detail')
        self.assertIn(str(run.id), url)
