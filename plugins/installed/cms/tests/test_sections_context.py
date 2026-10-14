"""Rendering a page's sections must not re-run every context processor per section.

``{% render_page_sections %}`` passed ``request=`` to ``render_to_string`` for each
section, which builds a fresh RequestContext and runs every context processor
(store settings, market, cart, nav caches) once per section — the bug
``{% storefront_blocks %}`` had on product pages (v0.77.0). The page's flattened
context already carries the processors' output.
"""

from __future__ import annotations

import copy

from django.conf import settings
from django.template import engines
from django.test import RequestFactory, TestCase, override_settings

CALLS: list[str] = []
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
            {
                'ctx_probe/section.html': '[{{ section_id }}:{{ settings.n }}:{{ counted_marker }}]',
                'cms/_menu.html': '<{{ menu.key }}:{{ counted_marker }}>',
            },
        )
    ]
    return cfg


class PageSectionsContextTests(TestCase):
    def setUp(self):
        from plugins.installed.cms.models import Page, PageSection
        from themes.sections import Section, section_registry

        previous = dict(section_registry._by_id)
        self.addCleanup(setattr, section_registry, '_by_id', previous)
        section_registry.register(
            Section(id='ctx_probe', label='Probe', template='ctx_probe/section.html')
        )
        CALLS.clear()
        self.page = Page.objects.create(title='Probe', slug='probe')
        for n in range(3):
            PageSection.objects.create(
                page=self.page, section_id='ctx_probe', settings={'n': n}, sort_order=n
            )

    @override_settings(TEMPLATES=_templates_with_probe())
    def test_context_processors_run_once_for_the_page_not_once_per_section(self):
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.backends.db import SessionStore

        request = RequestFactory().get('/probe/')
        request.session = SessionStore()
        request.user = AnonymousUser()
        template = engines['django'].from_string('{% load cms %}{% render_page_sections page %}')

        out = template.render({'page': self.page}, request=request)

        self.assertEqual(out, '[ctx_probe:0:yes][ctx_probe:1:yes][ctx_probe:2:yes]')
        self.assertEqual(CALLS, ['/probe/'])

    @override_settings(TEMPLATES=_templates_with_probe())
    def test_menus_reuse_the_page_context_too(self):
        from unittest import mock

        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.backends.db import SessionStore

        request = RequestFactory().get('/probe/')
        request.session = SessionStore()
        request.user = AnonymousUser()
        template = engines['django'].from_string(
            '{% load cms %}{% cms_menu "header" %}{% cms_menu "footer" %}'
        )
        with mock.patch(
            'plugins.installed.cms.services.get_menu', side_effect=lambda key: {'key': key}
        ):
            out = template.render({}, request=request)
        self.assertEqual(out, '<header:yes><footer:yes>')
        self.assertEqual(CALLS, ['/probe/'])
