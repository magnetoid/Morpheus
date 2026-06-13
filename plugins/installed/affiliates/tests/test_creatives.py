"""Affiliate marketing creatives — affiliate browse page + merchant model."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


def _approved_affiliate(username='cr', handle='cr'):
    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    u = get_user_model().objects.create_user(
        username=username, email=f'{username}@x.test', password='pw'
    )
    prog, _ = AffiliateProgram.objects.get_or_create(slug='default', defaults={'name': 'Default'})
    aff = Affiliate.objects.create(program=prog, user=u, handle=handle, status='approved')
    return u, aff


class AffiliateCreativesTests(TestCase):
    def setUp(self):
        self.user, self.aff = _approved_affiliate()
        self.client.force_login(self.user)

    def test_empty_renders(self):
        r = self.client.get('/affiliates/me/creatives/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Marketing creatives')

    def test_active_creative_shown_with_make_link_form(self):
        from plugins.installed.affiliates.models import AffiliateCreative

        AffiliateCreative.objects.create(
            title='Summer banner', landing_url='/products/x/', swipe_copy='Read this:'
        )
        r = self.client.get('/affiliates/me/creatives/')
        self.assertContains(r, 'Summer banner')
        self.assertContains(r, '/affiliates/me/links/new/')  # one-click make-link
        self.assertContains(r, '/products/x/')

    def test_inactive_creative_hidden(self):
        from plugins.installed.affiliates.models import AffiliateCreative

        AffiliateCreative.objects.create(title='Hidden one', is_active=False)
        r = self.client.get('/affiliates/me/creatives/')
        self.assertNotContains(r, 'Hidden one')
