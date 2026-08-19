"""What a query parameter does to a page — and what it must never do.

A storefront listing multiplies: category × sort × facet × facet × campaign tag.
Every combination is a fetchable URL, so the rules deciding which of them are
real pages are the store's main lever over how its crawl budget is spent. They
were one global on/off switch until v0.50.

The test that matters most here is `test_a_no_indexed_page_is_its_own_canonical`.
The arrangement it replaces set `noindex` on a facet page *and* pointed its
canonical at the bare category — two claims about two different URLs, and the
documented consequence is that the no-index can be applied to the canonical
target. A store could hold back its filter pages and lose the category with them.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from plugins.installed.seo.models import IndexRule, SiteSeoSettings
from plugins.installed.seo.rules import decide_params
from plugins.installed.seo.rules.params import (
    RECOMMENDED_RULES,
    blocked_param_patterns,
    captures_reserved,
)


class ParamPolicyTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_an_unlisted_parameter_consolidates_by_default(self):
        """A store gains parameters faster than a merchant writes rules for
        them, so the default has to be the safe one."""
        self.assertEqual(decide_params('ref=newsletter').query, '')

    def test_consolidate_drops_the_parameter_and_keeps_the_page_indexable(self):
        IndexRule.objects.create(param='sort', policy=IndexRule.POLICY_CONSOLIDATE)
        decision = decide_params('sort=price')
        self.assertEqual(decision.query, '')
        self.assertFalse(decision.noindex)

    def test_a_no_indexed_page_is_its_own_canonical(self):
        """The headline fix. Never `noindex` + a canonical naming another URL."""
        IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_NOINDEX)
        decision = decide_params('genre=crime')
        self.assertTrue(decision.noindex)
        self.assertEqual(decision.noindex_params, ('genre',))
        self.assertEqual(decision.query, 'genre=crime')

    def test_tracking_is_still_stripped_from_a_no_indexed_page(self):
        """Self-canonical means "this page", not "this URL byte for byte" — a
        campaign tag is never part of a page's identity."""
        IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_NOINDEX)
        IndexRule.objects.create(param='utm_*', policy=IndexRule.POLICY_CONSOLIDATE)
        self.assertEqual(decide_params('genre=crime&utm_source=news').query, 'genre=crime')

    def test_an_allowlisted_value_is_a_real_page(self):
        IndexRule.objects.create(
            param='genre', policy=IndexRule.POLICY_ALLOWLIST, allowed_values=['crime']
        )
        decision = decide_params('genre=crime')
        self.assertFalse(decision.noindex)
        self.assertEqual(decision.query, 'genre=crime')

    def test_a_value_off_the_allowlist_is_held_back(self):
        IndexRule.objects.create(
            param='genre', policy=IndexRule.POLICY_ALLOWLIST, allowed_values=['crime']
        )
        decision = decide_params('genre=westerns')
        self.assertTrue(decision.noindex)
        # …and still self-canonical, for the same reason as above.
        self.assertEqual(decision.query, 'genre=westerns')

    def test_a_wildcard_matches_a_family(self):
        IndexRule.objects.create(param='utm_*', policy=IndexRule.POLICY_CONSOLIDATE)
        self.assertEqual(decide_params('utm_source=x&utm_medium=y&utm_campaign=z').query, '')

    def test_a_longer_wildcard_wins(self):
        """Same first-match-wins precedence as the redirect resolver."""
        IndexRule.objects.create(param='utm_*', policy=IndexRule.POLICY_CONSOLIDATE)
        IndexRule.objects.create(param='utm_special_*', policy=IndexRule.POLICY_NOINDEX)
        self.assertTrue(decide_params('utm_special_thing=1').noindex)
        self.assertFalse(decide_params('utm_source=1').noindex)

    def test_an_inactive_rule_does_nothing(self):
        IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_NOINDEX, is_active=False)
        self.assertFalse(decide_params('genre=crime').noindex)

    def test_the_canonical_is_ordered_and_de_duplicated(self):
        """`?b=2&a=1` and `?a=1&b=2` are one page; publishing two canonicals for
        it splits whatever the page had earned in half."""
        IndexRule.objects.create(param='a', policy=IndexRule.POLICY_NOINDEX)
        IndexRule.objects.create(param='b', policy=IndexRule.POLICY_NOINDEX)
        self.assertEqual(decide_params('b=2&a=1').query, decide_params('a=1&b=2').query)
        self.assertEqual(decide_params('a=1&b=2&a=1').query, 'a=1&b=2')

    def test_a_blocked_parameter_is_never_no_indexed(self):
        """robots.txt stops the fetch, so the page's own directives are never
        read. Labelling a page nobody visits is theatre."""
        IndexRule.objects.create(param='filter', policy=IndexRule.POLICY_BLOCK)
        decision = decide_params('filter=x')
        self.assertFalse(decision.noindex)
        self.assertEqual(decision.query, '')

    def test_blocked_parameters_become_robots_patterns(self):
        IndexRule.objects.create(param='filter', policy=IndexRule.POLICY_BLOCK)
        IndexRule.objects.create(param='track_*', policy=IndexRule.POLICY_BLOCK)
        IndexRule.objects.create(param='sort', policy=IndexRule.POLICY_CONSOLIDATE)
        patterns = blocked_param_patterns()
        self.assertIn('/*?*filter=', patterns)
        # A wildcard keeps no `=`: the parameter name continues past the prefix,
        # so `/*?*track_=` would match nothing a store actually serves.
        self.assertIn('/*?*track_', patterns)
        self.assertNotIn('/*?*track_=', patterns)
        self.assertNotIn('/*?*sort=', patterns)


class ReservedPageParamTests(TestCase):
    """`page` takes no rule: pagination has a policy of its own."""

    def setUp(self):
        cache.clear()

    def test_page_two_survives_into_the_canonical(self):
        self.assertEqual(decide_params('page=2', paginated=True).query, 'page=2')

    def test_page_one_collapses(self):
        self.assertEqual(decide_params('page=1', paginated=True).query, '')

    def test_page_is_dropped_when_the_view_does_not_paginate(self):
        """`/shop/?page=999` on a listing that shows everything on one screen is
        not page 999 — it is the listing, plus noise. Echoing it into a
        self-canonical was minting one indexable duplicate per integer, and this
        is how it was doing it in production: the listing had no paginator at
        all, so no view-level fix could have reached it."""
        self.assertEqual(decide_params('page=999').query, '')

    def test_a_zero_padded_page_one_is_still_page_one(self):
        """A paginator reads `int(value)`, so `?page=01` renders page 1. Compared
        as a string it would keep a canonical of its own — a second address for
        the first page of a listing."""
        self.assertEqual(decide_params('page=01', paginated=True).query, '')
        self.assertEqual(decide_params('page=%2B1', paginated=True).query, '')

    def test_a_page_value_that_is_not_a_number_is_not_a_page(self):
        self.assertEqual(decide_params('page=abc', paginated=True).query, '')

    def test_a_wildcard_that_would_block_page_emits_no_robots_pattern(self):
        """`page*` set to block would put `Disallow: /*?*page` in robots.txt and
        stop crawlers reaching page 2 of every listing. The reservation has to
        hold for every spelling that reaches `page`, not just the literal name."""
        IndexRule.objects.create(param='page*', policy=IndexRule.POLICY_BLOCK)
        IndexRule.objects.create(param='p*', policy=IndexRule.POLICY_BLOCK)
        self.assertEqual(blocked_param_patterns(), ())

    def test_captures_reserved_names_the_spellings_that_reach_page(self):
        self.assertTrue(captures_reserved('page'))
        self.assertTrue(captures_reserved('page*'))
        self.assertTrue(captures_reserved('p*'))
        self.assertFalse(captures_reserved('price_*'))
        self.assertFalse(captures_reserved('pages'))

    def test_a_rule_cannot_capture_page(self):
        """The one thing a merchant must not be able to do by accident is
        canonicalise page 2 onto page 1, which de-indexes every product that is
        not on the first screen."""
        IndexRule.objects.create(param='page', policy=IndexRule.POLICY_CONSOLIDATE)
        self.assertEqual(decide_params('page=2', paginated=True).query, 'page=2')

    def test_a_wildcard_cannot_capture_page_either(self):
        IndexRule.objects.create(param='p*', policy=IndexRule.POLICY_CONSOLIDATE)
        self.assertEqual(decide_params('page=2', paginated=True).query, 'page=2')


class CacheInvalidationTests(TestCase):
    """A rule that keeps applying after you deleted it is worse than one that
    never worked."""

    def setUp(self):
        cache.clear()

    def test_creating_a_rule_takes_effect_immediately(self):
        self.assertFalse(decide_params('genre=crime').noindex)  # warms the cache
        IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_NOINDEX)
        self.assertTrue(decide_params('genre=crime').noindex)

    def test_deleting_a_rule_takes_effect_immediately(self):
        rule = IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_NOINDEX)
        self.assertTrue(decide_params('genre=crime').noindex)
        rule.delete()
        self.assertFalse(decide_params('genre=crime').noindex)


class LegacySettingsTests(TestCase):
    """An upgrading store's existing configuration keeps working.

    `noindex_query_params` was the whole of this feature before v0.50. Dropping
    its reader the moment a better table exists is how a merchant's setting goes
    quiet without anything reporting it.
    """

    def setUp(self):
        cache.clear()

    def test_the_old_settings_list_still_no_indexes(self):
        SiteSeoSettings.objects.create(noindex_query_params=['genre'])
        self.assertTrue(decide_params('genre=crime').noindex)

    def test_a_real_rule_overrides_the_old_list(self):
        SiteSeoSettings.objects.create(noindex_query_params=['genre'])
        IndexRule.objects.create(param='genre', policy=IndexRule.POLICY_CONSOLIDATE)
        decision = decide_params('genre=crime')
        self.assertFalse(decision.noindex)
        self.assertEqual(decision.query, '')

    def test_editing_the_old_list_takes_effect_immediately(self):
        """The list is compiled into the cached ruleset, so its own settings page
        needs to drop that cache too — otherwise the merchant edits the field,
        reloads the storefront, sees no change and concludes it is broken."""
        settings_row = SiteSeoSettings.objects.create(noindex_query_params=[])
        self.assertFalse(decide_params('genre=crime').noindex)  # warms the cache
        settings_row.noindex_query_params = ['genre']
        settings_row.save()
        self.assertTrue(decide_params('genre=crime').noindex)

    def test_the_old_list_gets_the_self_canonical_treatment_too(self):
        """The legacy path used to strip the parameter *and* no-index — the
        contradiction this release exists to remove."""
        SiteSeoSettings.objects.create(noindex_query_params=['genre'])
        self.assertEqual(decide_params('genre=crime').query, 'genre=crime')


class RuleFormTests(TestCase):
    """The editor has to refuse what the engine reserves.

    A form that accepts `page*` while rejecting `page` is not enforcing a
    reservation, it is enforcing a spelling.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username='rules_admin', email='rules@x.io', password='pw'
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.staff)
        self.url = reverse('seo_dashboard:index_rules')

    def _post(self, param, policy='block'):
        return self.client.post(
            self.url, {'action': 'create', 'param': param, 'policy': policy}, follow=True
        )

    def test_a_rule_for_page_is_refused(self):
        self._post('page')
        self.assertFalse(IndexRule.objects.filter(param='page').exists())

    def test_a_wildcard_that_would_capture_page_is_refused(self):
        for spelling in ('page*', 'p*', 'PAGE*'):
            with self.subTest(param=spelling):
                self._post(spelling)
                self.assertFalse(IndexRule.objects.filter(param=spelling.lower()).exists())

    def test_the_refusal_says_why(self):
        response = self._post('page*')
        self.assertContains(response, 'page number')

    def test_an_ordinary_wildcard_is_accepted(self):
        self._post('utm_*', policy='consolidate')
        self.assertTrue(IndexRule.objects.filter(param='utm_*').exists())

    def test_the_recommended_set_is_idempotent(self):
        self.client.post(self.url, {'action': 'seed'}, follow=True)
        first = IndexRule.objects.count()
        self.client.post(self.url, {'action': 'seed'}, follow=True)
        self.assertEqual(IndexRule.objects.count(), first)

    def test_no_recommended_rule_is_one_the_form_would_refuse(self):
        """A starter set that seeds a rule the editor rejects would be a rule
        the merchant can never edit or re-create."""
        for param, _policy, _note in RECOMMENDED_RULES:
            self.assertFalse(captures_reserved(param), param)


class RuleNormalisationTests(TestCase):
    def test_a_rule_is_normalised_on_save(self):
        """Rules arrive from the dashboard, a shell and an import; one stored as
        ` Genre ` matches nothing while looking correct in the table."""
        rule = IndexRule.objects.create(
            param='  Genre ', policy=IndexRule.POLICY_ALLOWLIST, allowed_values=[' crime ', '']
        )
        rule.refresh_from_db()
        self.assertEqual(rule.param, 'genre')
        self.assertEqual(rule.allowed_values, ['crime'])
