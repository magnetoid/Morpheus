"""Store-bootstrap plugin.

One-prompt store seed. A merchant types a single concept sentence and
the platform generates a brand voice, a small category structure, and
10-12 starter products via the active LLM. The marquee AI-first
onboarding moment.

Surfaces:
  - DashboardPage at /dashboard/apps/store_bootstrap/start/
  - Linked from the dashboard home command bar's "Bootstrap a store"
    chip (admin_dashboard/templates/admin_dashboard/home.html)
"""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin

logger = logging.getLogger('morpheus.store_bootstrap')


class StoreBootstrapPlugin(Plugin):
    name = 'store_bootstrap'
    label = 'Store bootstrap'
    version = '1.0.0'
    description = (
        'One-prompt store seed. A merchant types a concept sentence; '
        'the platform generates brand voice, category structure, and '
        'starter products through the active LLM gateway.'
    )
    has_models = False
    requires = ['catalog', 'ai_assistant', 'ai_content']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.store_bootstrap.urls',
            prefix='dashboard/apps/store_bootstrap/',
            namespace='store_bootstrap',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Bootstrap a store',
                slug='start',
                view='plugins.installed.store_bootstrap.views.bootstrap_view',
                icon='wand-2',
                section='ai',
                order=15,
                nav='settings',
            ),
        ]
