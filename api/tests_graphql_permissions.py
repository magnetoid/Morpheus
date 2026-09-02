"""Permission-boundary tests for the GraphQL scope seam.

Locks the v0.55.0 critical fix: a Bearer MCP/agent token resolves to a shared
is_staff=True service user, so the is_staff fallback in has_scope() used to
grant EVERY scope to ANY valid token — a catalog.read token passed admin:seo,
read:orders, cms.write, … The token's own stashed graphql scope set must decide.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from api.graphql_permissions import has_scope


class _Info:
    """Minimal strawberry.Info stand-in — only context['request'] is read."""

    def __init__(self, request):
        self.context = {'request': request}


def _req(*, staff=False, graphql_scopes=None):
    req = RequestFactory().post('/graphql/')
    User = get_user_model()
    req.user = User.objects.create_user(
        username=f'u-{staff}-{graphql_scopes}',
        email='u@example.test',
        password='pw',
        is_staff=staff,
    )
    if graphql_scopes is not None:
        # apply_bearer_user stashes this when a Bearer token is present.
        req._morph_token_scopes_graphql = set(graphql_scopes)
    return req


class HasScopeTokenBoundaryTests(TestCase):
    def test_scoped_token_is_confined_to_its_scopes(self):
        # The whole bug: a token scoped to catalog.read resolves to an
        # is_staff service user, but must NOT thereby pass admin scopes.
        info = _Info(_req(staff=True, graphql_scopes={'catalog.read'}))
        self.assertTrue(has_scope(info, 'catalog.read'))
        for denied in ('admin:seo', 'read:orders', 'cms.write', 'admin:marketplace'):
            self.assertFalse(has_scope(info, denied), f'{denied} must be denied')

    def test_wildcard_token_passes_anything(self):
        info = _Info(_req(staff=True, graphql_scopes={'*'}))
        self.assertTrue(has_scope(info, 'admin:seo'))
        self.assertTrue(has_scope(info, 'anything.at.all'))

    def test_empty_token_scope_set_denies(self):
        info = _Info(_req(staff=True, graphql_scopes=set()))
        self.assertFalse(has_scope(info, 'catalog.read'))

    def test_session_staff_without_a_token_keeps_the_is_staff_fallback(self):
        # No _morph_token_scopes_graphql attribute → a genuine dashboard staff
        # session, which legitimately holds every scope.
        info = _Info(_req(staff=True, graphql_scopes=None))
        self.assertTrue(has_scope(info, 'admin:seo'))

    def test_anonymous_without_a_token_is_denied(self):
        req = RequestFactory().post('/graphql/')
        req.user = AnonymousUser()
        self.assertFalse(has_scope(_Info(req), 'catalog.read'))


class VendorOrderIsolationTests(TestCase):
    """myVendorOrders must return only the caller's own vendor rows (IDOR)."""

    def _vendor_with_owner(self, name, slug):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.customers.models import Customer

        owner = Customer.objects.create_user(
            username=f'owner-{slug}', email=f'{slug}@ex.test', password='pw'
        )
        return Vendor.objects.create(name=name, slug=slug, owner=owner), owner

    def test_vendor_sees_only_own_orders(self):
        from plugins.installed.marketplace.graphql.queries import MarketplaceQueryExtension
        from plugins.installed.marketplace.models import VendorOrder
        from plugins.installed.orders.models import Order

        va, owner_a = self._vendor_with_owner('Vendor A', 'vendor-a')
        vb, _ = self._vendor_with_owner('Vendor B', 'vendor-b')

        order = Order.objects.create(
            email='c@ex.test',
            subtotal=Money(Decimal('30'), 'USD'),
            total=Money(Decimal('30'), 'USD'),
        )
        VendorOrder.objects.create(
            parent_order=order,
            vendor=va,
            gross=Money(Decimal('10'), 'USD'),
            net=Money(Decimal('9'), 'USD'),
        )
        VendorOrder.objects.create(
            parent_order=order,
            vendor=vb,
            gross=Money(Decimal('20'), 'USD'),
            net=Money(Decimal('18'), 'USD'),
        )

        req = RequestFactory().post('/graphql/')
        req.user = owner_a
        req._morph_token_scopes_graphql = {'vendor:self'}

        rows = MarketplaceQueryExtension().my_vendor_orders(_Info(req))
        self.assertEqual([r.vendor_name for r in rows], ['Vendor A'])


class CapabilitySeamTests(TestCase):
    """Session staff are authorized through the RBAC capability seam.

    GraphQL consulted core/authz.py NOWHERE before v0.59.0, so a role revoked in
    the dashboard still had full GraphQL access. The seam is MODE-AWARE: under
    the default `log` mode a failed check still returns True (recording the
    would-be denial), so wiring it changes no behaviour until a merchant flips
    enforcement.
    """

    def test_mapped_scope_routes_through_check(self):
        from unittest.mock import patch

        info = _Info(_req(staff=True))
        with patch('core.authz.check', return_value=True) as mock_check:
            self.assertTrue(has_scope(info, 'admin:seo'))
        mock_check.assert_called_once()
        # mapped to the seo.write capability, not the raw scope string
        self.assertEqual(mock_check.call_args[0][1], 'seo.write')

    def test_enforce_mode_denial_propagates(self):
        from unittest.mock import patch

        info = _Info(_req(staff=True))
        with patch('core.authz.check', return_value=False):
            self.assertFalse(has_scope(info, 'admin:seo'))

    def test_unmapped_scope_keeps_is_staff_fallback(self):
        # An unmapped scope must never accidentally deny — adding a resolver
        # should not require touching the mapping table to keep working.
        info = _Info(_req(staff=True))
        self.assertTrue(has_scope(info, 'some:brand-new-scope'))

    def test_token_callers_are_unaffected_by_the_seam(self):
        # A Bearer token is judged by its own scopes, never the capability seam.
        info = _Info(_req(staff=True, graphql_scopes={'catalog.read'}))
        self.assertTrue(has_scope(info, 'catalog.read'))
        self.assertFalse(has_scope(info, 'admin:seo'))
