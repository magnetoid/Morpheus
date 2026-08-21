"""SeoTemplate grammar + resolution precedence."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product
from plugins.installed.seo.models import SeoTemplate
from plugins.installed.seo.services.meta import resolve_meta
from plugins.installed.seo.services.templating import invalidate_templates, render_template


def _product(name='The Last Archive', slug='the-last-archive', category=None) -> Product:
    return Product.objects.create(
        name=name,
        slug=slug,
        sku=f'SKU-{slug}',
        status='active',
        price=Money(Decimal('9.00'), 'USD'),
        category=category,
    )


class GrammarTests(TestCase):
    def setUp(self):
        self.product = _product()

    def test_plain_token(self):
        self.assertEqual(
            render_template('{name} — buy online', self.product), 'The Last Archive — buy online'
        )

    def test_fallback_chain_and_literal(self):
        # `nonexistent` resolves empty → the quoted literal steps in.
        self.assertEqual(
            render_template('{nonexistent|"Anonymous"} wrote {name}', self.product),
            'Anonymous wrote The Last Archive',
        )

    def test_filters(self):
        self.assertEqual(render_template('{name|lower}', self.product), 'the last archive')
        out = render_template('{name|truncate:8}', self.product)
        self.assertLessEqual(len(out), 8)
        self.assertTrue(out.endswith('…'))

    def test_bracket_block_vanishes_when_empty(self):
        # No {author} on this product → the whole bracket (with its " by ")
        # disappears instead of dangling as "The Last Archive by".
        self.assertEqual(render_template('{name}[ by {author}]', self.product), 'The Last Archive')

    def test_template_with_no_resolving_token_declines(self):
        """Boilerplate with only dead tokens must return '', not publish
        bare separators as a page title."""
        self.assertEqual(render_template('{ghost} — {phantom}', self.product), '')

    def test_graphql_dict_object(self):
        """The PDP renders a GraphQL dict — the kind that matters most must
        expand (the old expand_tokens no-ops on dicts)."""
        pdp = {'name': 'Peter Pan', 'category': {'name': 'Fiction', 'slug': 'fiction'}}
        self.assertEqual(render_template('{name} — {category}', pdp), 'Peter Pan — Fiction')

    def test_deferred_money_fields_do_not_kill_the_render(self):
        """The PDP loads products with .only(), and a deferred djmoney column
        raises KeyError straight THROUGH getattr's default (the v0.46/v0.49
        landmine, third bite — unguarded it cost the whole pattern on every
        live PDP while every ORM-loaded test stayed green). One unreadable
        column must cost one empty token, never the render."""
        deferred = Product.objects.only('id', 'name', 'slug').get(pk=self.product.pk)
        self.assertEqual(
            render_template('{name} — buy online', deferred, 'product'),
            'The Last Archive — buy online',
        )


class ResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Fiction', slug='fiction')
        self.product = _product(category=self.category)

    def _title(self):
        return resolve_meta(obj=self.product, fallback_title='Fallback', page_kind='product').title

    def test_empty_only_fills_the_gap(self):
        SeoTemplate.objects.create(kind='product', field='title', template='{name} | branded')
        self.assertEqual(self._title(), 'The Last Archive | branded')

    def test_empty_only_loses_to_a_typed_value(self):
        """The P1 lesson holds: a merchant's own meta title beats the pattern."""
        self.product.meta_title = 'Hand-written title'
        self.product.save()
        SeoTemplate.objects.create(kind='product', field='title', template='{name} | branded')
        self.assertEqual(self._title(), 'Hand-written title')

    def test_all_mode_deliberately_overrides(self):
        self.product.meta_title = 'Hand-written title'
        self.product.save()
        SeoTemplate.objects.create(
            kind='product', field='title', template='{name} | rebrand', mode=SeoTemplate.MODE_ALL
        )
        self.assertEqual(self._title(), 'The Last Archive | rebrand')

    def test_scoped_rule_beats_global(self):
        SeoTemplate.objects.create(kind='product', field='title', template='{name} | global')
        SeoTemplate.objects.create(
            kind='product', field='title', scope='fiction', template='{name} | fiction'
        )
        self.assertEqual(self._title(), 'The Last Archive | fiction')

    def test_declining_template_falls_through_to_the_guess(self):
        """autofill mints a SeoMeta guess (the product name) on creation; a
        declining pattern restores that pre-template status quo, not the
        caller fallback."""
        SeoTemplate.objects.create(kind='product', field='title', template='{ghost} only')
        self.assertEqual(self._title(), 'The Last Archive')

    def test_no_page_kind_means_no_template_layer(self):
        """Panels and previews resolve without kind — patterns must not leak
        into surfaces that never asked for them. (The autofill guess is what
        resolves there, exactly as before this layer existed.)"""
        SeoTemplate.objects.create(kind='product', field='title', template='{name} | branded')
        got = resolve_meta(obj=self.product, fallback_title='Fallback').title
        self.assertNotIn('branded', got)

    def test_save_invalidates_the_compiled_cache(self):
        SeoTemplate.objects.create(kind='product', field='title', template='{name} | one')
        self.assertEqual(self._title(), 'The Last Archive | one')
        row = SeoTemplate.objects.get()
        row.template = '{name} | two'
        row.save()  # post_save must drop the compiled cache
        self.assertEqual(self._title(), 'The Last Archive | two')

    def test_inactive_rule_is_ignored(self):
        SeoTemplate.objects.create(
            kind='product', field='title', template='{name} | off', is_active=False
        )
        invalidate_templates()
        self.assertNotIn('off', self._title())


class DashboardPageTests(TestCase):
    URL = '/dashboard/seo/templates/'

    def _staff(self):
        User = get_user_model()
        return User.objects.create_user(
            username='seo@example.com',
            email='seo@example.com',
            password='pw-12345',
            is_staff=True,
            is_superuser=True,
        )

    def test_anonymous_is_redirected(self):
        self.assertEqual(self.client.get(self.URL).status_code, 302)

    def test_staff_can_create_and_preview(self):
        self.client.force_login(self._staff())
        _product()
        # create
        response = self.client.post(
            self.URL,
            {
                'action': 'create',
                'kind': 'product',
                'field': 'title',
                'template': '{name} | shop',
                'mode': 'empty_only',
                'priority': '100',
                'is_active': '1',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SeoTemplate.objects.count(), 1)
        # preview renders against a real product without saving another row
        response = self.client.post(self.URL, {'action': 'preview', 'template': '{name} | preview'})
        self.assertContains(response, 'The Last Archive | preview')
        self.assertEqual(SeoTemplate.objects.count(), 1)

    def test_pattern_without_a_token_is_rejected(self):
        self.client.force_login(self._staff())
        self.client.post(
            self.URL,
            {'action': 'create', 'kind': 'product', 'field': 'title', 'template': 'no tokens'},
        )
        self.assertEqual(SeoTemplate.objects.count(), 0)
