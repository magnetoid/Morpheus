"""Exact-value tests for the smart blend, exploration floor, and explain_block (M2)."""

from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product
from plugins.installed.dynamics.models import BanditArm, DynamicBlock, DynamicGridItem
from plugins.installed.dynamics.services import (
    SMART_WEIGHTS,
    explain_block,
    exploration_picks,
    recommend,
    smart_scored,
)


def _product(slug, category=None):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug,
        status='active',
        category=category,
        price=Money(Decimal('10'), 'USD'),
    )


def _grid(product, probability):
    return DynamicGridItem.objects.create(
        product=product, title=product.name, purchase_probability=probability
    )


def _block(**kw):
    defaults = {'name': 'Smart', 'strategy': 'smart', 'limit': 4}
    defaults.update(kw)
    return DynamicBlock.objects.create(**defaults)


def _request(session_slugs=None):
    req = RequestFactory().get('/')
    req.session = {'recently_viewed': session_slugs or []}
    return req


class SmartScoreMathTests(TestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(SMART_WEIGHTS.values()), 1.0)

    def test_probability_dominates(self):
        low = _product('low-prob')
        high = _product('high-prob')
        _grid(low, 0.1)
        _grid(high, 0.9)
        scored = smart_scored(_block(), request=_request())
        by_pk = {pid: (score, comps) for pid, score, comps in scored}
        # Exact component values: no views (trend 0), no session (0),
        # recency: high-prob is newest (idx 0 → 1.0), low-prob idx 1 → 0.0.
        self.assertEqual(by_pk[high.pk][1]['probability'], 0.9)
        self.assertAlmostEqual(by_pk[high.pk][0], 0.5 * 0.9 + 0.1 * 1.0)
        self.assertAlmostEqual(by_pk[low.pk][0], 0.5 * 0.1 + 0.1 * 0.0)
        self.assertEqual(scored[0][0], high.pk)

    def test_session_affinity_boosts_matching_category(self):
        fiction = Category.objects.create(name='Fiction', slug='fiction')
        poetry = Category.objects.create(name='Poetry', slug='poetry')
        viewed = _product('viewed-book', category=fiction)
        match = _product('match', category=fiction)
        other = _product('other', category=poetry)
        _grid(match, 0.2)
        _grid(other, 0.2)
        scored = smart_scored(_block(), request=_request(session_slugs=[viewed.slug]))
        by_pk = {pid: comps for pid, _, comps in scored}
        self.assertEqual(by_pk[match.pk]['session'], 1.0)
        self.assertEqual(by_pk[other.pk]['session'], 0.0)

    def test_empty_catalog_returns_empty(self):
        self.assertEqual(smart_scored(_block(), request=_request()), [])


class ExplorationFloorTests(TestCase):
    def setUp(self):
        # 10 products; the 'proven' ones carry high probability + many trials,
        # the two newest have no arms (never shown).
        self.proven = []
        for i in range(8):
            p = _product(f'proven-{i}')
            _grid(p, 0.9 - i * 0.01)
            BanditArm.objects.create(product=p, segment='all', trials=100, alpha=5, beta=5)
            self.proven.append(p)
        self.fresh_a = _product('fresh-a')
        self.fresh_b = _product('fresh-b')

    def test_exploration_picks_prefers_untried(self):
        picks = exploration_picks(_block(), exclude=set(), count=2)
        self.assertEqual(set(picks), {self.fresh_a.pk, self.fresh_b.pk})

    def test_floor_reserves_tail_positions(self):
        block = _block(limit=10, exploration_rate=0.2)  # ceil(0.2*10)=2 explore slots
        products = recommend(block, request=_request())
        pks = [p.pk for p in products]
        self.assertEqual(len(pks), 10)
        # The two never-shown products made the slate despite zero probability.
        self.assertIn(self.fresh_a.pk, pks)
        self.assertIn(self.fresh_b.pk, pks)

    def test_zero_rate_disables_floor(self):
        block = _block(limit=8, exploration_rate=0.0)
        pks = {p.pk for p in recommend(block, request=_request())}
        self.assertNotIn(self.fresh_a.pk, pks)


class DiversityCapTests(TestCase):
    def test_cap_limits_category_head(self):
        fiction = Category.objects.create(name='Fiction', slug='fiction')
        poetry = Category.objects.create(name='Poetry', slug='poetry')
        for i in range(4):
            _grid(_product(f'fic-{i}', category=fiction), 0.9)
        outsider = _product('poem', category=poetry)
        _grid(outsider, 0.05)
        block = _block(limit=3, diversity_cap=2, exploration_rate=0.0)
        products = recommend(block, request=_request())
        # Cap=2 fiction in the head → the poetry title takes slot 3.
        self.assertEqual(products[2].pk, outsider.pk)


class ExplainBlockTests(TestCase):
    def test_breakdown_components_and_flags(self):
        star = _product('star')
        pinned = _product('pinned')
        _grid(star, 0.8)
        block = _block(limit=4, exploration_rate=0.0, pinned_product_ids=[str(pinned.pk)])
        rows = explain_block(block, request=_request())
        by_slug = {r['product'].slug: r for r in rows}
        self.assertIn('pinned', by_slug['pinned']['flags'])
        comps = by_slug['star']['components']
        self.assertEqual(set(comps), {'probability', 'trend', 'session', 'recency'})
        self.assertEqual(comps['probability'], 0.8)
        # Pins always outrank the AI ranking.
        self.assertEqual(rows[0]['product'].pk, pinned.pk)

    def test_non_smart_strategy_still_explains_probability(self):
        p = _product('bestseller')
        _grid(p, 0.7)
        block = _block(strategy='probability_grid', limit=4)
        rows = explain_block(block, request=_request())
        self.assertTrue(rows)
        self.assertEqual(rows[0]['score'], 0.7)
        self.assertEqual(rows[0]['components'], {})
