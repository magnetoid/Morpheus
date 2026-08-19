"""robots.txt is assembled from contributions, and the assembly must not fail quiet.

Until v0.50 the seo app hardcoded `Disallow: /cart/`, `/checkout/` and `/auth/`
— three route shapes belonging to `storefront`. Moving them behind
`SEO_ROBOTS_RULES` fixes the ownership, and introduces the failure mode every
contribution seam has: if the subscriber never runs, the file still renders, 200
and well-formed, simply missing the lines. Nothing reports it. So the first test
here asserts the contributed lines are actually present — it is the only thing
standing between a refactor and a silently permissive robots.txt.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.seo.models import IndexRule
from plugins.installed.seo.services.crawler_files import render_robots_txt


class RobotsContributionTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_storefront_private_paths_are_present(self):
        """These come from `storefront.app.on_robots_rules`, not from seo."""
        body = render_robots_txt()
        for path in ('/cart/', '/checkout/', '/auth/'):
            self.assertIn(f'Disallow: {path}', body)

    def test_the_chrome_paths_seo_owns_are_present(self):
        body = render_robots_txt()
        self.assertIn('Disallow: /admin/', body)
        self.assertIn('Disallow: /dashboard/', body)

    def test_every_group_receives_the_disallows(self):
        """A path worth blocking is worth blocking for every crawler. The file
        has one group per AI crawler plus the `*` fallback, and a rule that
        landed in only one of them would be a hole shaped like whichever bot was
        listed first."""
        body = render_robots_txt()
        groups = [g for g in body.split('\n\n') if 'User-agent:' in g and 'Disallow: /\n' not in g]
        self.assertGreater(len(groups), 3)
        for group in groups:
            if 'Allow: /' in group:  # a group that is not blocked wholesale
                self.assertIn('Disallow: /cart/', group)

    def test_a_blocked_parameter_reaches_robots_txt(self):
        IndexRule.objects.create(param='filter', policy=IndexRule.POLICY_BLOCK)
        self.assertIn('Disallow: /*?*filter=', render_robots_txt())

    def test_other_policies_do_not_reach_robots_txt(self):
        """`block` is the only policy that stops a fetch. A no-indexed page has
        to be fetched for its no-index to be read at all."""
        IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_NOINDEX)
        IndexRule.objects.create(param='sort', policy=IndexRule.POLICY_CONSOLIDATE)
        body = render_robots_txt()
        self.assertNotIn('genre', body)
        self.assertNotIn('/*?*sort=', body)

    def test_search_is_not_disallowed(self):
        """Site search is already `noindex, follow` through its page kind. A
        `Disallow` would stop a crawler ever seeing that directive, freezing any
        search URL already in an index instead of removing it."""
        self.assertNotIn('Disallow: /search/', render_robots_txt())

    def test_the_sitemap_index_is_advertised(self):
        self.assertIn('Sitemap: ', render_robots_txt())
