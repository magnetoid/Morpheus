"""Who may read and who may change the SEO dashboard.

Every one of these screens was `@staff_member_required` and nothing else, so any
staff account could rewrite the store's canonical URLs, its robots directives
and its redirect table. The capabilities exist (`seo.read` / `seo.write`, held by
admin, marketing_manager and content_editor); they were simply never checked.

Enforcement defaults to `log` — a gate denies nobody until a merchant turns it
on — so every test here flips to `enforce` and puts it back. Without that flip a
test passes no matter what capability string the view names, which makes it
worse than no test at all.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

# Read surfaces and the write actions on them. The six pages that serve a list
# on GET and a mutation on POST appear in both lists on purpose: that split is
# the thing under test.
_READ_URLS = [
    'seo_dashboard:overview',
    'seo_dashboard:not_found',
    'seo_dashboard:redirects',
    'seo_dashboard:index_rules',
    'seo_dashboard:audit',
    'seo_dashboard:keywords',
    'seo_dashboard:bulk_meta',
    'seo_dashboard:sitemap',
    'seo_dashboard:settings',
    'seo_dashboard:schema_index',
]


def _set_mode(mode: str) -> None:
    from plugins.registry import app_registry

    plugin = app_registry.get('rbac')
    plugin.set_config('enforcement_mode', mode)
    plugin.invalidate_config_cache()


class SeoDashboardBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.rbac.models import Role

        # rbac seeds its roles in ready(), which runs before the test database
        # exists, so the table is empty here.
        Role.ensure_system_roles()
        user_model = get_user_model()
        cls.anonymous_url = reverse('seo_dashboard:overview')
        cls.shopper = user_model.objects.create_user(
            username='seo_shopper', email='shopper@x.io', password='pw'
        )
        cls.bare_staff = user_model.objects.create_user(
            username='seo_bare_staff', email='bare@x.io', password='pw', is_staff=True
        )
        cls.marketer = user_model.objects.create_user(
            username='seo_marketer', email='marketer@x.io', password='pw', is_staff=True
        )

    def setUp(self):
        from plugins.installed.rbac.services import grant

        grant(self.marketer, 'marketing_manager')
        _set_mode('enforce')
        self.addCleanup(_set_mode, 'log')

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(self.anonymous_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])

    def test_a_signed_in_shopper_gets_nowhere(self):
        self.client.force_login(self.shopper)
        response = self.client.get(self.anonymous_url)
        self.assertNotEqual(response.status_code, 200)

    def test_staff_without_the_capability_is_refused_every_read_surface(self):
        """The gap this closes: `is_staff` alone used to be the whole check."""
        self.client.force_login(self.bare_staff)
        for name in _READ_URLS:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_a_marketing_manager_may_read_every_surface(self):
        self.client.force_login(self.marketer)
        for name in _READ_URLS:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def _become_read_only(self):
        """A staff user holding seo.read and nothing else."""
        from plugins.installed.rbac.models import Role
        from plugins.installed.rbac.services import grant

        reader_role, _ = Role.objects.get_or_create(
            slug='seo_reader', defaults={'name': 'SEO reader', 'capabilities': ['seo.read']}
        )
        reader_role.capabilities = ['seo.read']
        reader_role.save()
        grant(self.bare_staff, 'seo_reader')
        self.client.force_login(self.bare_staff)

    def test_every_page_that_reads_and_writes_refuses_the_write(self):
        """Each page below serves a list on GET and a mutation on POST from one
        view function, so the read is gated by the decorator and the write by an
        explicit check inside the POST branch. Every one of those checks is
        covered here — testing a single representative view would let the other
        seven be deleted without a failure.
        """
        self._become_read_only()
        posts = {
            'seo_dashboard:settings': {'organization_name': 'Hijacked'},
            'seo_dashboard:audit': {},
            'seo_dashboard:keywords': {'keyword': 'free money'},
            'seo_dashboard:bulk_meta': {'meta_x': 'y'},
            'seo_dashboard:sitemap': {'action': 'save_toggles'},
            'seo_dashboard:redirects': {
                'action': 'create',
                'from_path': '/a/',
                'to_path': '/b/',
            },
            'seo_dashboard:index_rules': {
                'action': 'create',
                'param': 'sort',
                'policy': 'noindex',
            },
            'seo_dashboard:not_found': {},
        }
        for name, payload in posts.items():
            with self.subTest(view=name):
                url = reverse(name)
                self.assertEqual(self.client.get(url).status_code, 200, 'read should be allowed')
                self.assertEqual(
                    self.client.post(url, payload).status_code,
                    403,
                    f'{name} accepted a write from a read-only role',
                )

        from plugins.installed.seo.models import IndexRule, Redirect, TrackedKeyword

        self.assertFalse(Redirect.objects.exists(), 'a refused POST still wrote a redirect')
        self.assertFalse(TrackedKeyword.objects.exists(), 'a refused POST still wrote a keyword')
        self.assertFalse(IndexRule.objects.exists(), 'a refused POST still wrote an index rule')

    def test_the_404_page_does_not_write_on_a_read(self):
        """Suggesting targets stores `suggested_target`; it used to run on every
        GET, which made a write reachable with a read capability."""
        from plugins.installed.seo.models import NotFoundLog

        NotFoundLog.objects.create(path='/missing/', hit_count=3)
        self.client.force_login(self.marketer)

        self.client.get(reverse('seo_dashboard:not_found'))

        self.assertEqual(NotFoundLog.objects.get(path='/missing/').suggested_target, '')
