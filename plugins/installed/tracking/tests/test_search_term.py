"""GA4's search event names what was searched.

SEARCH_PERFORMED carries `query`; the handler read `search_term`, so every
search reached GA4 with no term (until v0.155).
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase


class SearchTermTests(TestCase):
    def test_the_events_query_is_the_search_term(self):
        from core.hooks import MorpheusEvents, hook_registry
        from plugins.registry import app_registry

        tracking = app_registry.get('tracking')
        with patch.object(tracking, '_fire') as fire:
            hook_registry.fire(MorpheusEvents.SEARCH_PERFORMED, query='dune', result_count=3)
        fire.assert_called_once()
        self.assertEqual(fire.call_args.kwargs['search_term'], 'dune')
