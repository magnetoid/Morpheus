"""TagProfile + tag-page rendering tests.

Tags have no description of their own (taggit), so TagProfile supplies the
editorial copy the ``?tag=`` landing page renders below its title.

The tag *filter* itself is exercised here too: ``Product`` has a UUID primary
key, so taggit must route through a UUID-typed through-model
(``catalog.UUIDTaggedItem``). With the default integer ``object_id`` the join
is ``uuid = integer`` — a 500 on Postgres that sqlite's loose typing hid. These
tests tag a real product and assert the filter matches, which only passes with
the UUID through-model wired up.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, TagProfile


class TagProfileModelTests(TestCase):
    def test_for_tag_resolves_by_slug_and_by_name(self):
        p = TagProfile.objects.create(
            slug='science-fiction', name='Science Fiction', description='Ray guns and big ideas.'
        )
        self.assertEqual(TagProfile.for_tag('science-fiction'), p)  # slug form
        self.assertEqual(TagProfile.for_tag('Science Fiction'), p)  # name → slugify → same
        self.assertIsNone(TagProfile.for_tag('nonexistent'))
        self.assertIsNone(TagProfile.for_tag(''))


class TagFilterTests(TestCase):
    """The tag filter must not 500 and must actually match tagged products."""

    def _make_product(self, name, slug):
        return Product.objects.create(
            name=name,
            slug=slug,
            sku=slug.upper(),
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
        )

    def test_tag_add_and_filter_match(self):
        # With the UUID through-model, tagging a UUID-PK product works (it used
        # to overflow taggit's integer object_id) …
        p = self._make_product('Dune', 'dune')
        p.tags.add('Science Fiction')
        # … and the ?tag= filter join resolves by name and by slug.
        from django.db.models import Q

        by_name = Product.objects.filter(Q(tags__name__iexact='Science Fiction'))
        by_slug = Product.objects.filter(Q(tags__slug__iexact='science-fiction'))
        self.assertIn(p, list(by_name))
        self.assertIn(p, list(by_slug))

    def test_tag_page_renders_for_unknown_tag(self):
        # No TagProfile, no tagged products — the page that 500'd on prod must 200.
        resp = Client().get('/products/?tag=nonexistenttag123')
        self.assertEqual(resp.status_code, 200)


class TagPageRenderTests(TestCase):
    def test_tag_page_shows_title_and_description(self):
        TagProfile.objects.create(
            slug='science-fiction', name='Science Fiction', description='Ray guns and big ideas.'
        )
        resp = Client().get('/products/?tag=science-fiction')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ray guns and big ideas.')  # description renders below title
        self.assertContains(resp, 'Science Fiction')  # tag name renders as the title
