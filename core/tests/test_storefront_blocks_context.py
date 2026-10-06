"""Rendering a slot's blocks must not re-run every context processor per block.

``{% storefront_blocks %}`` passed ``request=`` to ``render_to_string``, which
builds a fresh ``RequestContext`` — and so runs EVERY context processor — once
per block. A live product page with ~50 block renders ran the store-settings
processor 50 times (101 queries), resolved the market 52 times and loaded the
cart 50 times; 80% of its 0.6 s server time was inside that tag. The blocks
already receive the page's flattened context, which carries the processors'
output, so the page's single run is the only one needed.
"""

from __future__ import annotations

import copy

from django.conf import settings
from django.template import engines
from django.test import RequestFactory, TestCase, override_settings

CALLS: list[str] = []
_SLOT = 'ctx_probe_slot'
_PROCESSOR = f'{__name__}.counting_processor'


def counting_processor(request):
    CALLS.append(request.path)
    return {'counted_marker': 'yes'}


def _templates_with_probe():
    cfg = copy.deepcopy(settings.TEMPLATES)
    opts = cfg[0]['OPTIONS']
    opts['context_processors'] = [*opts['context_processors'], _PROCESSOR]
    opts['loaders'] = [
        (
            'django.template.loaders.locmem.Loader',
            {'ctx_probe/block.html': '[{{ block.slot }}:{{ counted_marker }}]'},
        )
    ]
    return cfg


class StorefrontBlocksContextTests(TestCase):
    def setUp(self):
        from plugins.contributions import StorefrontBlock
        from plugins.registry import app_registry

        CALLS.clear()
        previous = app_registry._storefront_blocks
        app_registry._storefront_blocks = [
            *previous,
            *(StorefrontBlock(slot=_SLOT, template='ctx_probe/block.html') for _ in range(3)),
        ]
        self.addCleanup(setattr, app_registry, '_storefront_blocks', previous)

    @override_settings(TEMPLATES=_templates_with_probe())
    def test_context_processors_run_once_for_the_page_not_once_per_block(self):
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.backends.db import SessionStore

        request = RequestFactory().get('/ctx-probe/')
        request.session = SessionStore()  # the processors expect a middleware-shaped request
        request.user = AnonymousUser()
        template = engines['django'].from_string(
            '{% load morph %}{% storefront_blocks "ctx_probe_slot" %}'
        )

        out = template.render({}, request=request)

        self.assertEqual(out.count(f'[{_SLOT}:yes]'), 3, out)
        self.assertEqual(CALLS, ['/ctx-probe/'])
