"""Every contributed dashboard page's link leads somewhere.

A ``DashboardPage`` is served at ``/dashboard/apps/<plugin>/<slug>/`` unless it
sets ``url``, in which case the sidebar links there instead — and nothing
checks that the plugin actually mounts that URL. eco_impact declared
``url='/dashboard/eco-impact/'`` and never routed it, so its nav entry 404'd on
the one store that has the app on.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.registry import app_registry


class ContributedPagesResolveTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            username='owner',
            email='owner@example.com',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(owner)

    def test_each_page_link_answers(self):
        pages = list(app_registry.dashboard_pages())
        self.assertGreater(len(pages), 50)
        broken = []
        for page in pages:
            href = page.url or f'/dashboard/apps/{page.plugin}/{page.slug}/'
            try:
                status = self.client.get(href).status_code
            except Exception as exc:  # noqa: BLE001 — report, don't stop at the first
                status = f'{type(exc).__name__}: {exc}'[:120]
            if status not in (200, 302):
                broken.append((page.plugin, page.slug, href, status))
        self.assertEqual(broken, [])
