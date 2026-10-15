# Wave 0 Live Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four live problems get fixed in one MINOR release (v0.113.0):
- Consent is checked before any server-side send.
- Every model call obeys the AI kill switch and the spend cap.
- Visitors no longer cost a session write.
- Three latent defects are closed: double webhook delivery, the ×31 attribution total, and unchecked staff-entered URLs.

**Architecture:**
- **Consent.** One core seam, `core/consent.py`, answered by the consent app through two new filters. The order records the shopper's choice at checkout, and every server-side sender asks `allowed()`.
- **AI guard.** The guard moves onto `core.agents.llm.LLMProvider` itself (`__init_subclass__`, as v0.104.0 did for ai_assistant's gateway). Model calls outside the agent runtime's own calls are counted in a new `ModelUsageDay` table.
- **Webhooks.** Core's dispatcher is the only trigger. A new `WEBHOOK_DELIVER` filter lets webhooks_ui take the delivery, keeping its log, retries and replay.
- **Outbound requests.** Staff-entered URLs go through a new `core.net.outbound_request`, which runs the private-network check and never follows redirects.

**Tech Stack:** Django 6.1, Celery, Strawberry GraphQL, django-money, the Morpheus hook bus (`core/hooks.py`), sqlite in-memory for tests.

**Spec:** `docs/superpowers/specs/2026-10-15-wave0-live-fixes-design.md`

## Global Constraints

- **The unmanaged rule.** A store "manages consent" when the consent app is active and `StoreSettings.gdpr_enabled` is on (default **True**). With the app off, or the switch off, every sender sends exactly as before.
- **Consent rule.** `allowed(category)` is `not managed or <category>`. An order's stamp beats the request, and the request beats the store-level answer.
- **No new plugin→plugin imports.** Every task keeps these at their current values:
  - core boundary 0,
  - plugin boundary 113,
  - plugin standard 38.

  Core never imports `plugins.installed.*`. Tests are exempt from both boundary scripts.
- **Linting.** ruff 0.15.8 (`.venv/bin/ruff`) runs `check .` and `format --check .`. `PLC0415` is ignored repo-wide, so inline imports need no `noqa`.
- **Test command** (written as `$TEST <labels>` below):
  `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace' .venv/bin/python manage.py test`
  Creating the test DB takes about 1–2 minutes, so run long label sets in the background and read the tail of the output.
- **Merchant messages.**
  - The guard's message is `guardrails.PAUSED_MESSAGE = 'AI is paused in Settings → Agent guardrails.'`
  - The spend-cap message is `guardrails.CAP_MESSAGE = "AI has reached today's spend limit set in Agent guardrails."`

  Both texts are unchanged from v0.104.0.
- **Commits.**
  - Every commit ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
  - Commits stay local on `main` until Task 14; a push to main deploys every store.
- **Version.** The version moves from v0.112.0 to **v0.113.0**, using `manage.py release --minor`.

## Review Focus

These are the failure modes the spec implies but most tasks never exercise. Each has a test in the task named.

1. **A payment confirmed hours after checkout** (a Stripe or PayPal webhook, staff "mark paid"). The stamp on the order decides, and no request is needed: a real stamped Order fired through `ORDER_PAID` must not reach Meta (Task 3).
2. **Two model calls on a fresh day in two workers.** The second must not lose its tokens to the `(day, model)` unique constraint. `record_model_usage` updates, then creates, then updates again (Task 6).
3. **webhooks_ui on, but its enqueue raises.** Core still posts exactly once and no event is lost (Task 10).
4. **The merchant switches consent management off after orders were stamped.** A stamped "no" still refuses, because the shopper never agreed (Task 1).
5. **A crawler on a consent-managed store** (no cookies). It gets no GA4 `view_item` send (Task 4) and no `sessionid` cookie (Task 9).

---

### Task 1: The consent seam (`core/consent.py`, answered by the consent app)

**Files:**
- Create: `core/consent.py`
- Modify:
  - `core/hooks.py` (add two filter constants after `AI_USAGE_TODAY`, ~line 742)
  - `plugins/installed/consent/services.py` (two answer functions)
  - `plugins/installed/consent/app.py` (`ready()` registers them)
- Test: `plugins/installed/consent/tests/test_server_side_consent.py`

**Interfaces:**
- Produces:
  - `core.consent.decision_for(request) -> dict` with keys `managed`, `analytics`, `marketing` (all bool).
  - `core.consent.stamp(request) -> dict` (same shape).
  - `core.consent.allowed(category: str, *, order=None, request=None) -> bool`, where `category` is `'marketing'` or `'analytics'`.
  - `core.consent.marketing_customer_ids() -> set | None`. `None` means no restriction, because the store does not manage consent.
  - Events `MorpheusEvents.CONSENT_DECISION = 'consent.decision'` and `MorpheusEvents.CONSENT_MARKETING_CUSTOMERS = 'consent.marketing_customers'`.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/consent/tests/test_server_side_consent.py`:

```python
"""Server-side sends ask one question: did this shopper agree?

The browser pixels have obeyed the banner since v0.91.0; the conversion APIs,
GA4 Measurement Protocol and audience uploads did not. ``core/consent.py``
answers for them: an order carries the shopper's choice from checkout (a
payment webhook has no visitor to ask), a request answers for its visitor,
and with neither the store-level answer applies — refuse when the store
manages consent, send when it does not.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from django.core.cache import cache
from django.test import RequestFactory, TestCase

from core.consent import allowed, decision_for, marketing_customer_ids, stamp
from plugins.installed.consent.models import ConsentLog
from plugins.installed.consent.services import COOKIE_NAME
from plugins.registry import app_registry


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _request(**flags):
    req = RequestFactory().get('/')
    if flags:
        req.COOKIES[COOKIE_NAME] = json.dumps({'necessary': True, **flags})
    return req


def _order(**consent):
    return SimpleNamespace(metadata={'consent': consent} if consent else {})


class DecisionTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def test_a_managed_store_with_no_cookie_grants_nothing(self):
        self.assertEqual(
            decision_for(_request()), {'managed': True, 'analytics': False, 'marketing': False}
        )

    def test_the_cookie_answers_per_category(self):
        d = decision_for(_request(marketing=True))
        self.assertEqual(d, {'managed': True, 'analytics': False, 'marketing': True})

    def test_no_request_means_no_visitor_and_nothing_granted(self):
        self.assertEqual(
            decision_for(None), {'managed': True, 'analytics': False, 'marketing': False}
        )

    def test_global_privacy_control_is_a_refusal(self):
        req = _request()
        req.META['HTTP_SEC_GPC'] = '1'
        self.assertFalse(allowed('marketing', request=req))

    def test_a_store_with_gdpr_off_is_unmanaged(self):
        _set_gdpr(False)
        self.assertTrue(allowed('marketing', request=_request()))
        self.assertTrue(allowed('analytics'))

    def test_with_the_consent_app_off_nothing_answers_and_the_store_is_unmanaged(self):
        self.addCleanup(app_registry.activate, 'consent')
        app_registry.deactivate('consent')
        self.assertEqual(
            decision_for(_request()), {'managed': False, 'analytics': False, 'marketing': False}
        )
        self.assertTrue(allowed('marketing'))

    def test_stamp_is_the_decision(self):
        self.assertEqual(stamp(_request(analytics=True)), decision_for(_request(analytics=True)))

    def test_an_unknown_category_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            allowed('functional')


class OrderStampTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def test_the_stamp_beats_the_request(self):
        order = _order(managed=True, analytics=False, marketing=False)
        self.assertFalse(allowed('marketing', order=order, request=_request(marketing=True)))

    def test_a_stamped_yes_is_allowed(self):
        self.assertTrue(allowed('marketing', order=_order(managed=True, marketing=True)))

    def test_an_order_stamped_unmanaged_is_allowed(self):
        self.assertTrue(allowed('analytics', order=_order(managed=False)))

    def test_an_unstamped_order_on_a_managed_store_is_refused(self):
        self.assertFalse(allowed('marketing', order=_order()))

    def test_an_unstamped_order_on_an_unmanaged_store_is_allowed(self):
        _set_gdpr(False)
        self.assertTrue(allowed('marketing', order=_order()))

    def test_a_stamped_no_still_refuses_after_management_is_switched_off(self):
        # Review Focus 4: the shopper never agreed; switching the banner off later
        # does not make their old order consent.
        order = _order(managed=True, marketing=False)
        _set_gdpr(False)
        self.assertFalse(allowed('marketing', order=order))


class MarketingCustomersTests(TestCase):
    def setUp(self):
        _set_gdpr(True)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.yes = User.objects.create_user(username='yes', email='y@x.test', password='x')
        self.changed = User.objects.create_user(username='chg', email='c@x.test', password='x')
        self.never = User.objects.create_user(username='nev', email='n@x.test', password='x')
        ConsentLog.objects.create(customer=self.yes, session_key='a', marketing=True)
        ConsentLog.objects.create(customer=self.changed, session_key='b', marketing=True)
        # The later decision wins.
        later = ConsentLog.objects.create(customer=self.changed, session_key='b', marketing=False)
        ConsentLog.objects.filter(pk=later.pk).update(
            created_at=ConsentLog.objects.get(customer=self.yes).created_at.replace(year=2099)
        )

    def test_only_the_latest_yes_counts(self):
        self.assertEqual(marketing_customer_ids(), {self.yes.pk})

    def test_an_unmanaged_store_has_no_restriction(self):
        _set_gdpr(False)
        self.assertIsNone(marketing_customer_ids())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.consent.tests.test_server_side_consent`
Expected: an ERROR on import, `ModuleNotFoundError: No module named 'core.consent'`.

- [ ] **Step 3: Add the two filter constants to `core/hooks.py`**

Insert directly after the line `AI_USAGE_TODAY = 'ai.usage_today'  # filter`:

```python

    # CONSENT_DECISION — filter, value=None, kwargs: request (HttpRequest or None).
    #   The consent app answers {'managed', 'analytics', 'marketing'} for that
    #   visitor; request=None means no visitor, so nothing is granted. Nothing
    #   answers while the app is off, which core/consent.py reads as "this store
    #   does not manage consent" — the same as the templates' `consent` context.
    CONSENT_DECISION = 'consent.decision'  # filter
    # CONSENT_MARKETING_CUSTOMERS — filter, value=None, no kwargs. The consent app
    #   answers the set of customer ids whose latest decision allows marketing
    #   (audience uploads read it through core.consent.marketing_customer_ids).
    CONSENT_MARKETING_CUSTOMERS = 'consent.marketing_customers'  # filter
```

- [ ] **Step 4: Create `core/consent.py`**

```python
"""Consent for what the server sends — one rule, read by every sender.

The browser-side rule (v0.91.0) is ``not consent.managed or consent.<category>``.
Server-side sends — conversion APIs, GA4 Measurement Protocol, audience uploads —
often run where no visitor is present (a payment webhook, a nightly job), so the
shopper's choice is recorded on the order at checkout (``metadata['consent']``)
and read back here.

Core never imports the consent app: it asks through ``CONSENT_DECISION`` and
``CONSENT_MARKETING_CUSTOMERS``. With the app off nothing answers, which reads
as "this store does not manage consent", exactly as the templates see it.
"""

from __future__ import annotations

CATEGORIES = ('analytics', 'marketing')
_UNMANAGED = {'managed': False, 'analytics': False, 'marketing': False}


def decision_for(request) -> dict:
    """The visitor's decision (``request=None``: no visitor, nothing granted)."""
    from core.hooks import MorpheusEvents, hook_registry

    answer = hook_registry.filter(MorpheusEvents.CONSENT_DECISION, None, request=request)
    if not isinstance(answer, dict):
        return dict(_UNMANAGED)
    return {
        'managed': bool(answer.get('managed')),
        'analytics': bool(answer.get('analytics')),
        'marketing': bool(answer.get('marketing')),
    }


def stamp(request) -> dict:
    """What an order records at checkout, read back by every later send."""
    return decision_for(request)


def _permits(decision: dict, category: str) -> bool:
    return not decision.get('managed') or bool(decision.get(category))


def allowed(category: str, *, order=None, request=None) -> bool:
    """May a server-side send of ``category`` data happen?

    The order's stamp decides when it has one; else the request's visitor; else
    the store: a store that manages consent refuses without evidence.
    """
    if category not in CATEGORIES:
        raise ValueError(f'unknown consent category: {category!r}')
    recorded = (getattr(order, 'metadata', None) or {}).get('consent') if order else None
    if isinstance(recorded, dict):
        return _permits(recorded, category)
    return _permits(decision_for(request), category)


def marketing_customer_ids() -> set | None:
    """Customers whose latest decision allows marketing; ``None`` when the store
    does not manage consent (no restriction). Fails closed to an empty set."""
    from core.hooks import MorpheusEvents, hook_registry

    if not decision_for(None)['managed']:
        return None
    answer = hook_registry.filter(MorpheusEvents.CONSENT_MARKETING_CUSTOMERS, None)
    return set(answer) if answer is not None else set()
```

- [ ] **Step 5: Add the consent app's answers to `plugins/installed/consent/services.py`**

Append at the end of the file:

```python


def decision_answer(value, request=None, **_):
    """CONSENT_DECISION: this visitor's choice, for core/consent.py."""
    from core.context_processors import _gdpr_enabled

    decision = read_consent_from_cookie(request)
    return {
        'managed': _gdpr_enabled(),
        'analytics': decision['analytics'],
        'marketing': decision['marketing'],
    }


def marketing_customers_answer(value, **_):
    """CONSENT_MARKETING_CUSTOMERS: customers whose LATEST decision allows marketing."""
    from plugins.installed.consent.models import ConsentLog

    latest: dict = {}
    rows = (
        ConsentLog.objects.filter(customer__isnull=False)
        .order_by('customer_id', '-created_at')
        .values_list('customer_id', 'marketing')
    )
    for customer_id, marketing in rows:
        latest.setdefault(customer_id, marketing)
    return {cid for cid, marketing in latest.items() if marketing}
```

(`read_consent_from_cookie(None)` already returns the necessary-only default.)

- [ ] **Step 6: Register the answers in `plugins/installed/consent/app.py`**

In `ready()`, directly after
`self.register_hook(events.CUSTOMER_DATA_EXPORT, gdpr.on_customer_export, priority=30)`, add:

```python
        # Server-side sends (core/consent.py) ask the same decision the templates read.
        from plugins.installed.consent import services  # noqa: PLC0415

        self.register_hook(events.CONSENT_DECISION, services.decision_answer, priority=50)
        self.register_hook(
            events.CONSENT_MARKETING_CUSTOMERS, services.marketing_customers_answer, priority=50
        )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `$TEST plugins.installed.consent morpheus.tests.test_events`
Expected: every test passes (the new module plus `test_gating` and the events mirror).

- [ ] **Step 8: Commit**

```bash
git add core/consent.py core/hooks.py plugins/installed/consent/services.py plugins/installed/consent/app.py plugins/installed/consent/tests/test_server_side_consent.py
git commit -m "feat(consent): one server-side consent rule — core/consent.py answered by the consent app

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The order records the shopper's choice at checkout

**Files:**
- Modify:
  - `plugins/installed/orders/services.py` (`_order_metadata` ~line 285, `create_from_cart` ~line 391)
  - `plugins/installed/orders/graphql/mutations.py` (`complete_order`, ~line 356)
  - `plugins/installed/agentic_checkout/views.py` (~line 778)
- Test:
  - `plugins/installed/orders/tests/test_consent_stamp.py`
  - `plugins/installed/agentic_checkout/tests/test_acp_complete.py` (one test added)

**Interfaces:**
- Consumes: `core.consent.stamp(request) -> dict` (Task 1).
- Produces:
  - `OrderService.create_from_cart(cart, email, shipping_address, billing_address, *, visitor_id='', consent: dict | None = None) -> Order`.
  - `order.metadata['consent'] = {'managed': bool, 'analytics': bool, 'marketing': bool}` whenever `consent` is passed.

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/orders/tests/test_consent_stamp.py`:

```python
"""The order carries the shopper's consent from checkout.

ORDER_PAID fires from a payment webhook, a staff click or an agent — never from
the shopper's browser — so the conversion APIs need the choice on the order.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.mutations import CompleteOrderInput, OrdersMutationExtension
from plugins.installed.orders.models import Cart, CartItem, Order
from plugins.installed.orders.services import CartService, OrderService


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


class CreateFromCartStampTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Stamp Book', slug='stamp-book', sku='STAMP', price=Money(10, 'USD'),
            status='active',
        )
        self.addr = {'first_name': 'S', 'last_name': 'T', 'line1': '1 Main', 'country': 'US'}

    def _cart(self, key):
        cart = CartService.get_or_create_cart(session_key=key)
        CartService.add_item(cart, str(self.product.id), quantity=1)
        return cart

    def test_the_consent_given_is_stored_on_the_order(self):
        consent = {'managed': True, 'analytics': True, 'marketing': False}
        order = OrderService.create_from_cart(
            self._cart('c1'), 'a@x.test', self.addr, self.addr, consent=consent
        )
        self.assertEqual(order.metadata['consent'], consent)

    def test_no_consent_argument_stores_no_stamp(self):
        order = OrderService.create_from_cart(self._cart('c2'), 'b@x.test', self.addr, self.addr)
        self.assertNotIn('consent', order.metadata)


class CompleteOrderPassesTheStampTests(TestCase):
    """The storefront checkout stamps the visitor's cookie decision."""

    def setUp(self):
        _set_gdpr(True)
        self.session = SessionStore()
        self.session.create()
        product = Product.objects.create(
            name='Routed', slug='stamp-routed', sku='STAMP-R', price=Money(Decimal('5'), 'USD'),
            status='active',
        )
        self.cart = Cart.objects.create(session_key=self.session.session_key)
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=1, unit_price=Money(Decimal('5'), 'USD')
        )

    def _info(self, cookie=None):
        request = RequestFactory().post('/graphql/')
        request.session = self.session
        request.user = AnonymousUser()
        if cookie is not None:
            request.COOKIES['morpheus_consent'] = json.dumps(cookie)
        info = mock.Mock()
        info.context = {'request': request}
        return info

    def _complete(self, info):
        order = Order.objects.create(
            email='s@x.test', subtotal=Money(Decimal('5'), 'USD'), total=Money(Decimal('5'), 'USD')
        )
        inp = CompleteOrderInput(
            cart_id=str(self.cart.pk), email='s@x.test',
            shipping_address=AddressInput(country='US'), payment_gateway='manual',
        )
        with (
            mock.patch(
                'plugins.installed.orders.services.OrderService.create_from_cart',
                return_value=order,
            ) as create,
            mock.patch(
                'plugins.installed.payments.services.routing.create_payment_intent_for',
                return_value={'success': True, 'client_secret': ''},
            ),
        ):
            OrdersMutationExtension().complete_order(info, inp)
        return create.call_args.kwargs['consent']

    def test_a_shopper_who_accepted_marketing_is_stamped_yes(self):
        consent = self._complete(self._info({'necessary': True, 'marketing': True}))
        self.assertEqual(consent, {'managed': True, 'analytics': False, 'marketing': True})

    def test_a_shopper_who_never_answered_is_stamped_no(self):
        consent = self._complete(self._info())
        self.assertEqual(consent, {'managed': True, 'analytics': False, 'marketing': False})
```

In `plugins/installed/agentic_checkout/tests/test_acp_complete.py`, add this method to the class that holds `test_complete_success_places_paid_order`:

```python
    def test_an_agent_order_records_no_marketing_consent(self):
        # An agent's request carries no consent cookie: on a store that manages
        # consent, the conversion APIs must not report this purchase.
        from django.core.cache import cache

        from core.models import StoreSettings

        row = StoreSettings.objects.first() or StoreSettings()
        row.gdpr_enabled = True
        row.save()
        cache.delete('morph:gdpr_enabled')
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK):
            self._complete(sid)
        self.assertEqual(
            Order.objects.get().metadata['consent'],
            {'managed': True, 'analytics': False, 'marketing': False},
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$TEST plugins.installed.orders.tests.test_consent_stamp plugins.installed.agentic_checkout.tests.test_acp_complete`
Expected: FAIL.
- `test_the_consent_given_is_stored_on_the_order` fails with `TypeError: create_from_cart() got an unexpected keyword argument 'consent'`.
- The `CompleteOrder…` tests fail with `KeyError: 'consent'`.
- The agentic test fails with `KeyError: 'consent'`.

- [ ] **Step 3: Store the stamp (`plugins/installed/orders/services.py`)**

Replace the `_order_metadata` signature and its first line:

```python
def _order_metadata(visitor_id: str, breakdown: dict, consent: dict | None = None) -> dict:
    """Order metadata, including any named charges the breakdown added on top
    of the priced lines (``Order.extra_lines``), so a receipt adds up."""
    metadata = {'visitor_id': visitor_id} if visitor_id else {}
    if consent is not None:
        # The shopper's choice at checkout; every server-side send reads it back
        # (core/consent.py) because a payment webhook has no visitor to ask.
        metadata['consent'] = dict(consent)
```

In `create_from_cart`, change the keyword-only parameters from

```python
        *,
        visitor_id: str = '',
    ) -> Order:
```

to

```python
        *,
        visitor_id: str = '',
        consent: dict | None = None,
    ) -> Order:
```

Then change `metadata=_order_metadata(visitor_id, breakdown),` to
`metadata=_order_metadata(visitor_id, breakdown, consent),`.

- [ ] **Step 4: Stamp at the storefront checkout (`plugins/installed/orders/graphql/mutations.py`)**

In `complete_order`, change the `create_from_cart(` call inside `with transaction.atomic():` to:

```python
                order = OrderService.create_from_cart(
                    cart=cart,
                    email=input.email,
                    shipping_address=ship,
                    billing_address=bill,
                    visitor_id=visitor_id,
                    consent=consent_stamp(request),
                )
```

and, directly above the `with transaction.atomic():` line, add:

```python
            from core.consent import stamp as consent_stamp
```

- [ ] **Step 5: Stamp agent orders (`plugins/installed/agentic_checkout/views.py`)**

In the `OrderService.create_from_cart(` call (~line 778), after the `visitor_id=…` argument add:

```python
            # An agent's request carries no consent cookie: on a store that
            # manages consent its order records "no", so no conversion API reports it.
            consent=consent_stamp(request),
```

Add `from core.consent import stamp as consent_stamp` to the module's imports, after `from django.views.decorators.http import require_http_methods` (line ~31). Core is always importable from an app.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `$TEST plugins.installed.orders plugins.installed.agentic_checkout plugins.installed.payments.tests.test_routing`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add plugins/installed/orders/services.py plugins/installed/orders/graphql/mutations.py plugins/installed/agentic_checkout/views.py plugins/installed/orders/tests/test_consent_stamp.py plugins/installed/agentic_checkout/tests/test_acp_complete.py
git commit -m "feat(orders): the order records the shopper's consent at checkout

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The five conversion APIs obey consent

**Files:**
- Modify the event handlers in:
  - `plugins/installed/meta_commerce/app.py` (~135–151)
  - `plugins/installed/tiktok_commerce/app.py` (~116–129)
  - `plugins/installed/pinterest_commerce/app.py` (~117–126)
  - `plugins/installed/snapchat_commerce/app.py` (~117)
  - `plugins/installed/reddit_ads/app.py` (~86)
- Modify `plugins/installed/storefront/views/cart.py`: pass `request=request` on the one `ADD_TO_CART` fire and both `REMOVE_FROM_CART` fires.
- Test: `plugins/tests_capi_consent.py` (repo-level, beside `plugins/tests_uninstalled_models.py`).

**Interfaces:**
- Consumes: `core.consent.allowed('marketing', order=…, request=…)` (Task 1). Order stamps come from Task 2.
- Produces: `ADD_TO_CART` and `REMOVE_FROM_CART` now carry `request=` (Task 4 reads it).

- [ ] **Step 1: Write the failing test**

Create `plugins/tests_capi_consent.py`:

```python
"""No conversion API sends what the shopper did not agree to.

Meta, TikTok, Pinterest, Snapchat and Reddit sent sha256(email) and the purchase
on ORDER_PAID whatever the shopper chose (wave 0 item 3). Each now asks
core.consent.allowed('marketing'): the order's stamp, else the request, else the
store — a store that manages consent refuses without evidence.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.registry import app_registry

PURCHASE = [
    ('meta_commerce', 'plugins.installed.meta_commerce.services.capi.send_purchase'),
    ('tiktok_commerce', 'plugins.installed.tiktok_commerce.services.events_api.send_complete_payment'),
    ('pinterest_commerce', 'plugins.installed.pinterest_commerce.services.capi.send_checkout'),
    ('snapchat_commerce', 'plugins.installed.snapchat_commerce.services.capi.send_purchase'),
    ('reddit_ads', 'plugins.installed.reddit_ads.services.capi.send_purchase'),
]
CART = [
    ('meta_commerce', '_on_add_to_cart', 'plugins.installed.meta_commerce.services.capi.send_add_to_cart', 'product'),
    ('meta_commerce', '_on_begin_checkout', 'plugins.installed.meta_commerce.services.capi.send_initiate_checkout', 'cart'),
    ('tiktok_commerce', '_on_add_to_cart', 'plugins.installed.tiktok_commerce.services.events_api.send_add_to_cart', 'product'),
    ('tiktok_commerce', '_on_begin_checkout', 'plugins.installed.tiktok_commerce.services.events_api.send_initiate_checkout', 'cart'),
    ('pinterest_commerce', '_on_add_to_cart', 'plugins.installed.pinterest_commerce.services.capi.send_add_to_cart', 'product'),
]


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _order(consent=None):
    return SimpleNamespace(metadata={'consent': consent} if consent is not None else {})


def _request(marketing=None):
    req = RequestFactory().get('/')
    if marketing is not None:
        req.COOKIES['morpheus_consent'] = json.dumps({'necessary': True, 'marketing': marketing})
    return req


class PurchaseConsentTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def _sent(self, app, path, order):
        with patch(path) as send:
            app_registry.get(app)._on_order_paid(order=order)
        return send.called

    def test_a_stamped_no_sends_nothing(self):
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertFalse(self._sent(app, path, _order({'managed': True, 'marketing': False})))

    def test_a_stamped_yes_sends(self):
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertTrue(self._sent(app, path, _order({'managed': True, 'marketing': True})))

    def test_an_unstamped_order_on_a_managed_store_sends_nothing(self):
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertFalse(self._sent(app, path, _order()))

    def test_a_store_that_does_not_manage_consent_sends_as_before(self):
        _set_gdpr(False)
        for app, path in PURCHASE:
            with self.subTest(app=app):
                self.assertTrue(self._sent(app, path, _order()))

    def test_a_real_paid_order_fired_through_the_bus_respects_its_stamp(self):
        # Review Focus 1: the payment webhook fires ORDER_PAID hours later with
        # the order alone; the stamp decides.
        from core.hooks import MorpheusEvents, hook_registry
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='late@x.test', subtotal=Money(Decimal('9'), 'USD'),
            total=Money(Decimal('9'), 'USD'),
            metadata={'consent': {'managed': True, 'analytics': True, 'marketing': False}},
        )
        with patch('plugins.installed.meta_commerce.services.capi.send_purchase') as send:
            hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
        send.assert_not_called()


class CartEventConsentTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def _sent(self, app, handler, path, arg, request):
        with patch(path) as send:
            getattr(app_registry.get(app), handler)(**{arg: object()}, request=request)
        return send.called

    def test_a_visitor_who_refused_is_not_sent(self):
        for app, handler, path, arg in CART:
            with self.subTest(app=app, handler=handler):
                self.assertFalse(self._sent(app, handler, path, arg, _request()))

    def test_a_visitor_who_accepted_is_sent(self):
        for app, handler, path, arg in CART:
            with self.subTest(app=app, handler=handler):
                self.assertTrue(self._sent(app, handler, path, arg, _request(marketing=True)))

    def test_an_unmanaged_store_sends_as_before(self):
        _set_gdpr(False)
        for app, handler, path, arg in CART:
            with self.subTest(app=app, handler=handler):
                self.assertTrue(self._sent(app, handler, path, arg, _request()))


class CartFiresCarryTheRequestTests(TestCase):
    def test_add_to_cart_passes_the_request(self):
        from core.hooks import MorpheusEvents, hook_registry
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Req', slug='req-carry', sku='REQ', price=Money(3, 'USD'), status='active'
        )
        seen = []

        def spy(**kw):
            seen.append(kw)

        hook_registry.register(MorpheusEvents.ADD_TO_CART, spy, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.ADD_TO_CART, spy)
        self.client.post(f'/cart/add/{product.id}/', {'quantity': 1})
        self.assertTrue(seen)
        self.assertIsNotNone(seen[0].get('request'))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.tests_capi_consent`
Expected: FAIL.
- `test_a_stamped_no_sends_nothing` and `test_an_unstamped_order_on_a_managed_store_sends_nothing` fail with `True is not false`.
- `test_a_visitor_who_refused_is_not_sent` fails the same way.
- `test_add_to_cart_passes_the_request` fails with `unexpectedly None`.

- [ ] **Step 3: Gate Meta (`plugins/installed/meta_commerce/app.py`)**

Replace the three handlers with:

```python
    def _on_order_paid(self, order=None, **_):
        from core.consent import allowed

        if order is None or not allowed('marketing', order=order):
            return
        self._capi(lambda m: m.send_purchase(order), 'purchase')

    def _on_add_to_cart(self, product=None, variant=None, quantity=1, request=None, **_):
        from core.consent import allowed

        if (product is None and variant is None) or not allowed('marketing', request=request):
            return
        self._capi(
            lambda m: m.send_add_to_cart(product=product, variant=variant, quantity=quantity),
            'add_to_cart',
        )

    def _on_begin_checkout(self, cart=None, request=None, **_):
        from core.consent import allowed

        if cart is None or not allowed('marketing', request=request):
            return
        self._capi(lambda m: m.send_initiate_checkout(cart), 'begin_checkout')
```

- [ ] **Step 4: Gate TikTok (`plugins/installed/tiktok_commerce/app.py`)**

```python
    def _on_order_paid(self, order=None, **_):
        from core.consent import allowed

        if order is not None and allowed('marketing', order=order):
            self._event(lambda m: m.send_complete_payment(order), 'complete_payment')

    def _on_add_to_cart(self, product=None, variant=None, quantity=1, request=None, **_):
        from core.consent import allowed

        if (product is not None or variant is not None) and allowed('marketing', request=request):
            self._event(
                lambda m: m.send_add_to_cart(product=product, variant=variant, quantity=quantity),
                'add_to_cart',
            )

    def _on_begin_checkout(self, cart=None, request=None, **_):
        from core.consent import allowed

        if cart is not None and allowed('marketing', request=request):
            self._event(lambda m: m.send_initiate_checkout(cart), 'begin_checkout')
```

- [ ] **Step 5: Gate Pinterest (`plugins/installed/pinterest_commerce/app.py`)**

```python
    def _on_order_paid(self, order=None, **_):
        from core.consent import allowed

        if order is not None and allowed('marketing', order=order):
            self._capi(lambda m: m.send_checkout(order), 'checkout')

    def _on_add_to_cart(self, product=None, variant=None, quantity=1, request=None, **_):
        from core.consent import allowed

        if (product is not None or variant is not None) and allowed('marketing', request=request):
            self._capi(
                lambda m: m.send_add_to_cart(product=product, variant=variant, quantity=quantity),
                'add_to_cart',
            )
```

- [ ] **Step 6: Gate Snapchat and Reddit**

In both `plugins/installed/snapchat_commerce/app.py` and `plugins/installed/reddit_ads/app.py`, change the guard at the top of `_on_order_paid` from

```python
        if order is None:
            return
```

to

```python
        from core.consent import allowed

        if order is None or not allowed('marketing', order=order):
            return
```

- [ ] **Step 7: Pass the request on the cart fires (`plugins/installed/storefront/views/cart.py`)**

Add `request=request,` as the last keyword argument to the `ADD_TO_CART` fire (in `cart_add`, after `quantity=quantity,`). Add it to both `REMOVE_FROM_CART` fires as well (after their `customer=…` argument).

- [ ] **Step 8: Run the tests to verify they pass**

Run: `$TEST plugins.tests_capi_consent plugins.installed.meta_commerce plugins.installed.tiktok_commerce plugins.installed.pinterest_commerce plugins.installed.snapchat_commerce plugins.installed.reddit_ads plugins.installed.storefront.tests.test_cart_checkout_wave1 plugins.installed.consent`
Expected: OK. If an existing app test drives an `ORDER_PAID` send through the bus and now sees nothing, set `_set_gdpr(False)` in that test's setUp, with the comment `# an unmanaged store sends as before; consent has its own tests (plugins/tests_capi_consent.py)`, and ledger it as a ruling.

- [ ] **Step 9: Commit**

```bash
git add plugins/tests_capi_consent.py plugins/installed/meta_commerce/app.py plugins/installed/tiktok_commerce/app.py plugins/installed/pinterest_commerce/app.py plugins/installed/snapchat_commerce/app.py plugins/installed/reddit_ads/app.py plugins/installed/storefront/views/cart.py
git commit -m "fix(channels): conversion APIs send only with marketing consent (wave 0 item 3)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

(The Snapchat pixel's hashed email already renders inside `{% if not consent.managed or consent.marketing %}` in `snapchat_commerce/blocks/pixel.html`, so the browser side needs no change.)

---

### Task 4: GA4 server events, the Google Ads tag, and the second banner

**Files:**
- Modify:
  - `plugins/installed/tracking/app.py` (handlers ~65–117 and `_fire`)
  - `plugins/installed/tracking/templatetags/tracking.py` (`gads_purchase_conversion`; delete `tracking_consent_banner`)
  - `plugins/installed/tracking/models.py` (delete `show_consent_banner`, `banner_accept_label`, `banner_reject_label`, `banner_body`, `banner_link_url`, `banner_placement` and `BANNER_PLACEMENT_CHOICES`)
  - `plugins/installed/tracking/views.py` (delete lines 148–153, the six banner assignments)
  - `plugins/installed/tracking/templates/tracking/settings.html` (delete everything from the `<hr class="my-3">` before the `show_consent_banner` checkbox through the closing `</label>` of the Placement select, keeping `<button class="btn btn-primary">Save consent</button>`)
  - the `{% tracking_consent_banner %}` line in each of these themes' `templates/storefront/base.html`:
    - `themes/library/supernatural_shop/` (line 713)
    - `themes/library/dot_books/` (line 702)
    - `themes/library/irving_survival/` (line 472)
  - `plugins/installed/tracking/tests/test_server_events.py` (setUp of `ViewItemFromProductPageTests`)
- Delete: `plugins/installed/tracking/templates/tracking/blocks/consent_banner.html`
- Create: `plugins/installed/tracking/migrations/0003_drop_second_banner.py` (generated)
- Test: `plugins/installed/tracking/tests/test_consent_gate.py`

**Interfaces:**
- Consumes:
  - `core.consent.allowed('analytics', order=…, request=…)` (Task 1).
  - The `request=` on cart events (Task 3).
  - The order stamp (Task 2).
- Produces: none.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/tracking/tests/test_consent_gate.py`:

```python
"""Server-side GA4 and the Google Ads tag obey the consent app; one banner.

GA4 Measurement Protocol events (view_item, add_to_cart, purchase, …) went out
whatever the visitor chose, the Ads purchase tag rendered on every confirmation
page, and the tracking app shipped a second cookie banner of its own.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.template import Context, Template, TemplateSyntaxError
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.registry import app_registry

_DELAY = 'plugins.installed.tracking.tasks.send_event_task.delay'
_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _order(consent, product=None):
    line = SimpleNamespace(product=product, variant=None, quantity=1, unit_price=Money(Decimal('5'), 'USD'))
    return SimpleNamespace(
        pk=1, order_number='ORD-C', items=SimpleNamespace(all=lambda: [line]),
        total=Money(Decimal('5'), 'USD'), shipping_total=None, tax_total=None,
        metadata={'consent': consent},
    )


class Ga4ConsentTests(TestCase):
    def setUp(self):
        _set_gdpr(True)
        self.product = Product.objects.create(
            name='Gate', slug='gate-probe', sku='GATE', price=Money(Decimal('4'), 'USD'),
            product_type='simple', status='active',
        )

    def test_a_visitor_with_no_decision_sends_no_view_item(self):
        # Review Focus 5: a crawler or a visitor who never answered the banner.
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        delay.assert_not_called()

    def test_a_visitor_who_accepted_analytics_sends_view_item(self):
        self.client.cookies['morpheus_consent'] = json.dumps({'necessary': True, 'analytics': True})
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(delay.call_args.kwargs['event_name'], 'view_item')

    def test_purchase_follows_the_orders_stamp(self):
        plugin = app_registry.get('tracking')
        with patch(_DELAY) as delay:
            plugin.on_order_paid(order=_order({'managed': True, 'analytics': False}, self.product))
        delay.assert_not_called()
        with patch(_DELAY) as delay:
            plugin.on_order_paid(order=_order({'managed': True, 'analytics': True}, self.product))
        self.assertEqual(delay.call_args.kwargs['event_name'], 'purchase')

    def test_an_unmanaged_store_sends_as_before(self):
        _set_gdpr(False)
        with patch(_DELAY) as delay:
            self.client.get('/products/gate-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(delay.call_args.kwargs['event_name'], 'view_item')


class AdsTagConsentTests(TestCase):
    def setUp(self):
        p = app_registry.get('tracking')
        p.set_config('google_ads_conversion_id', 'AW-123')
        p.set_config('google_ads_purchase_label', 'abc')
        self.addCleanup(p.set_config, 'google_ads_conversion_id', '')
        self.addCleanup(p.set_config, 'google_ads_purchase_label', '')
        self.order = _order({'managed': True})

    def _render(self, consent):
        ctx = {'order': self.order}
        if consent is not None:
            ctx['consent'] = consent
        return Template('{% load tracking %}{% gads_purchase_conversion order %}').render(
            Context(ctx)
        )

    def test_no_tag_without_marketing_consent(self):
        self.assertEqual(self._render({'managed': True, 'marketing': False}), '')

    def test_tag_with_marketing_consent(self):
        self.assertIn('"conversion"', self._render({'managed': True, 'marketing': True}))

    def test_tag_on_a_store_without_the_consent_app(self):
        self.assertIn('"conversion"', self._render(None))


class OneBannerTests(TestCase):
    def test_the_second_banner_tag_is_gone(self):
        with self.assertRaises(TemplateSyntaxError):
            Template('{% load tracking %}{% tracking_consent_banner %}')

    def test_no_theme_renders_it(self):
        root = Path(settings.BASE_DIR) / 'themes' / 'library'
        for base in root.glob('*/templates/storefront/base.html'):
            with self.subTest(theme=base.parts[-4]):
                self.assertNotIn('tracking_consent_banner', base.read_text())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.tracking.tests.test_consent_gate`
Expected: FAIL.
- `test_a_visitor_with_no_decision_sends_no_view_item` fails with `Expected 'delay' to not have been called`.
- `test_no_tag_without_marketing_consent` fails because the rendered tag contains the script.
- Both `OneBannerTests` fail.

- [ ] **Step 3: Gate GA4 in `plugins/installed/tracking/app.py`**

The handlers below pass the request (or order) through to `_fire`; `on_order_paid` and `on_refund` already pass `order`.

```python
    def on_add_to_cart(
        self, cart=None, item=None, product=None, variant=None, quantity=1, request=None, **_
    ):
        if product is None:
            return
        self._fire(
            'add_to_cart', cart=cart, item=item, product=product, variant=variant,
            quantity=quantity, request=request,
        )

    def on_remove_from_cart(self, cart=None, item=None, product=None, quantity=1, request=None, **_):
        if product is None:
            return
        self._fire(
            'remove_from_cart', cart=cart, item=item, product=product, quantity=quantity,
            request=request,
        )

    def on_begin_checkout(self, cart=None, request=None, **_):
        if cart is None:
            return
        self._fire('begin_checkout', cart=cart, request=request)
```

The other handlers change as follows:
- In `on_product_viewed`, change `self._fire('view_item', product=product)` to `self._fire('view_item', product=product, request=request)`.
- In `on_login`, change the signature to `(self, customer=None, request=None, **_)` and the body to `self._fire('login', customer=customer, request=request)`.
- In `on_search`, change the signature to `(self, search_term='', request=None, **_)` and the body to `self._fire('search', search_term=search_term, request=request)`.

In `_fire`, insert directly after the docstring, before the `try:` that imports `event_mapping`:

```python
        # Consent first (core/consent.py): the order's stamp, else the visitor's
        # request, else the store — a store that manages consent sends nothing
        # it cannot show the shopper agreed to (sign_up has neither: not sent).
        from core.consent import allowed

        if not allowed('analytics', order=ctx.get('order'), request=ctx.pop('request', None)):
            return
```

(`ctx.pop('request')` keeps the request out of the builders.)

- [ ] **Step 4: Gate the Ads tag and delete the second banner (`templatetags/tracking.py`)**

Change the decorator and signature of `gads_purchase_conversion`, and add the consent check right after the `if not order:` guard:

```python
@register.simple_tag(takes_context=True)
def gads_purchase_conversion(context, order):
```

```python
    if not order:
        return ''
    # The consent app's decision (absent when the app is off: an unmanaged store).
    consent = context.get('consent') or {}
    if consent.get('managed') and not consent.get('marketing'):
        return ''
```

Delete the whole `tracking_consent_banner` function, with its `@register.simple_tag` decorator. Then delete `plugins/installed/tracking/templates/tracking/blocks/consent_banner.html` (`git rm`).

- [ ] **Step 5: Remove the banner's settings**
  - **`plugins/installed/tracking/models.py`:** delete `BANNER_PLACEMENT_CHOICES` (lines 68–72) and the six fields `show_consent_banner` through `banner_placement` (lines 138–147).
  - **`plugins/installed/tracking/views.py`:** delete the six `s.show_consent_banner …` to `s.banner_placement …` lines in the `consent` action.
  - **`plugins/installed/tracking/templates/tracking/settings.html`:** delete the `<hr class="my-3">` before the banner checkbox and every banner label, input, textarea and select after it. The `Save consent` button stays.
  - **Themes:** in each of the three themes' `base.html`, delete the line `{% tracking_consent_banner %}`.

Then generate the migration:

Run: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations tracking -n drop_second_banner`
Expected: `plugins/installed/tracking/migrations/0003_drop_second_banner.py` with six `RemoveField` operations.

- [ ] **Step 6: Keep the old GA4 tests on an unmanaged store**

In `plugins/installed/tracking/tests/test_server_events.py`, add a module-level helper and call it at the start of `ViewItemFromProductPageTests.setUp`:

```python
def _unmanaged_store():
    """These tests are about what GA4 receives; consent has its own tests
    (test_consent_gate.py), so run them on a store that does not manage it."""
    from django.core.cache import cache

    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = False
    row.save()
    cache.delete('morph:gdpr_enabled')
```

```python
    def setUp(self):
        _unmanaged_store()
        self.product = Product.objects.create(
```

- [ ] **Step 7: Run the tests to verify they pass, and compile the changed templates**

Run: `$TEST plugins.installed.tracking plugins.installed.storefront.tests.test_gdpr_toggle themes`
Expected: OK.

Run:
```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','morph.settings');django.setup();from django.template.loader import get_template as g;[g(t) for t in ('tracking/settings.html',)];from django.template import engines;e=engines['django'];[e.from_string(open(p).read()) for p in ('themes/library/supernatural_shop/templates/storefront/base.html','themes/library/dot_books/templates/storefront/base.html','themes/library/irving_survival/templates/storefront/base.html')];print('compiled')"
```
Expected: `compiled`.

- [ ] **Step 8: Commit**

```bash
git add -A plugins/installed/tracking themes/library/supernatural_shop/templates/storefront/base.html themes/library/dot_books/templates/storefront/base.html themes/library/irving_survival/templates/storefront/base.html
git commit -m "fix(tracking): GA4 server events and the Ads tag obey consent; one cookie banner

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `meta.sync_audience` uploads only consenting non-staff customers, with approval

**Files:**
- Modify:
  - `plugins/installed/meta_commerce/agent_tools.py` (the `@tool(name='meta.sync_audience', …)` decorator)
  - `plugins/installed/meta_commerce/services/audiences.py` (`_segment_emails`)
  - `plugins/installed/meta_commerce/tests/test_api.py` (`test_sync_uploads_hashed_emails_only`: unmanaged store)
- Test: `plugins/installed/meta_commerce/tests/test_audience_consent.py`

**Interfaces:**
- Consumes: `core.consent.marketing_customer_ids() -> set | None` (Task 1) and the order stamp (Task 2).
- Produces: none.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/meta_commerce/tests/test_audience_consent.py`:

```python
"""Custom-audience uploads: never staff, only customers who said yes, and only
with the merchant's approval.

`meta.sync_audience` uploaded every user with an email — staff included — under
scope `analytics.read` with no approval (wave 0 item 3).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.consent.models import ConsentLog
from plugins.installed.meta_commerce.services.audiences import _segment_emails
from plugins.installed.orders.models import Order

User = get_user_model()


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


class AllCustomersTests(TestCase):
    def setUp(self):
        self.yes = User.objects.create_user(username='y', email='yes@x.test', password='x')
        self.no = User.objects.create_user(username='n', email='no@x.test', password='x')
        self.staff = User.objects.create_user(
            username='s', email='staff@x.test', password='x', is_staff=True
        )
        ConsentLog.objects.create(customer=self.yes, session_key='a', marketing=True)
        ConsentLog.objects.create(customer=self.staff, session_key='b', marketing=True)

    def test_a_managed_store_uploads_only_customers_who_said_yes(self):
        _set_gdpr(True)
        self.assertEqual(_segment_emails('all_customers'), ['yes@x.test'])

    def test_staff_are_never_uploaded(self):
        _set_gdpr(False)
        emails = _segment_emails('all_customers')
        self.assertIn('no@x.test', emails)
        self.assertNotIn('staff@x.test', emails)


class PurchasersTests(TestCase):
    def _order(self, email, consent):
        o = Order.objects.create(
            email=email, subtotal=Money(Decimal('5'), 'USD'), total=Money(Decimal('5'), 'USD'),
            metadata={'consent': consent} if consent else {},
        )
        Order.objects.filter(pk=o.pk).update(status='confirmed')
        return o

    def test_a_managed_store_uploads_only_stamped_yes_purchasers(self):
        _set_gdpr(True)
        self._order('buyer-yes@x.test', {'managed': True, 'marketing': True})
        self._order('buyer-no@x.test', {'managed': True, 'marketing': False})
        self._order('buyer-old@x.test', None)
        self.assertEqual(_segment_emails('purchasers'), ['buyer-yes@x.test'])


class ToolGateTests(TestCase):
    def test_the_tool_needs_approval_and_a_customer_write_scope(self):
        from core.agents.registry import agent_registry

        tool = agent_registry.get_tool('meta.sync_audience')
        self.assertTrue(tool.requires_approval)
        self.assertEqual(tool.scopes, ['crm.write'])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.meta_commerce.tests.test_audience_consent`
Expected: FAIL.
- The `all_customers` test fails, listing three emails.
- `test_staff_are_never_uploaded` fails with `'staff@x.test' unexpectedly found`.
- The purchasers test fails with three emails.
- The tool test fails with `False is not true`.

- [ ] **Step 3: Filter the segments (`plugins/installed/meta_commerce/services/audiences.py`)**

Replace `_segment_emails` with:

```python
def _segment_emails(segment: str) -> list[str]:
    """Emails for one segment: never staff, and on a store that manages consent
    only shoppers who agreed to marketing (core/consent.py)."""
    from core.consent import marketing_customer_ids  # noqa: PLC0415

    if segment == 'all_customers':
        from django.contrib.auth import get_user_model  # noqa: PLC0415

        qs = (
            get_user_model()
            .objects.exclude(email='')
            .exclude(is_staff=True)
            .exclude(is_superuser=True)
        )
        allowed_ids = marketing_customer_ids()
        if allowed_ids is not None:
            qs = qs.filter(pk__in=allowed_ids)
        return sorted(qs.values_list('email', flat=True))
    if segment == 'purchasers':
        from datetime import timedelta  # noqa: PLC0415

        from django.utils import timezone  # noqa: PLC0415

        from core.consent import allowed  # noqa: PLC0415
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        since = timezone.now() - timedelta(days=180)
        orders = (
            Order.objects.filter(placed_at__gte=since)
            .exclude(status__in=['pending', 'cancelled'])
            .exclude(email='')
            .exclude(customer__is_staff=True)
            .only('email', 'metadata')
        )
        return sorted({o.email for o in orders if allowed('marketing', order=o)})
    return []
```

(Asking `allowed()` per order keeps one rule. A 180-day purchaser list is small, and `marketing_customer_ids` would not cover guest checkouts.)

If `Order.placed_at` is null on a freshly created row, the purchasers test fails on the `placed_at__gte` filter. In that case set `placed_at=timezone.now()` in the test's `_order` helper and ledger the change.

- [ ] **Step 4: Gate the tool (`plugins/installed/meta_commerce/agent_tools.py`)**

In the `meta.sync_audience` decorator, replace `scopes=['analytics.read'],` with:

```python
    # Uploads customer data off the store: a write, and only on the merchant's yes.
    scopes=['crm.write'],
    requires_approval=True,
```

- [ ] **Step 5: Keep the existing upload test on an unmanaged store**

In `plugins/installed/meta_commerce/tests/test_api.py::AudienceTests.test_sync_uploads_hashed_emails_only`, insert before `_connect()`:

```python
        # Hashing and upload shape only; who may be uploaded is test_audience_consent.
        from django.core.cache import cache

        from core.models import StoreSettings

        row = StoreSettings.objects.first() or StoreSettings()
        row.gdpr_enabled = False
        row.save()
        cache.delete('morph:gdpr_enabled')
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `$TEST plugins.installed.meta_commerce plugins.installed.agent_mcp.tests.test_linda_turn core.agents.tests`
Expected: OK. The scope vocabulary test passes, because `crm.write` is in `AVAILABLE_SCOPES`.

- [ ] **Step 7: Commit**

```bash
git add plugins/installed/meta_commerce/agent_tools.py plugins/installed/meta_commerce/services/audiences.py plugins/installed/meta_commerce/tests/test_api.py plugins/installed/meta_commerce/tests/test_audience_consent.py
git commit -m "fix(meta): audience sync skips staff and non-consenting shoppers, needs approval

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Every provider call obeys the guardrails and is counted

**Files:**
- Modify:
  - `core/agents/guardrails.py` (add `PAUSED_MESSAGE`, `CAP_MESSAGE`, `AIPaused`, `model_call_refusal`, `run_scope`, `guard_model_call`, `record_model_usage`; extend `daily_spend_usd`)
  - `core/agents/models.py` (add `ModelUsageDay`)
  - `core/models.py` (re-export `ModelUsageDay` beside the other agent models at ~line 321)
  - `core/agents/llm.py` (`LLMProvider.__init_subclass__`)
  - `core/agents/runtime.py` (wrap the two `self.provider.respond(` calls in `run_scope()`)
  - `plugins/installed/ai_assistant/services/llm.py` (`AIPaused` and `guardrail_refusal` come from core)
- Create: `core/migrations/0023_modelusageday.py` (generated)
- Test: `core/agents/tests/test_provider_guard.py`

**Interfaces:**
- Produces:
  - `core.agents.guardrails.AIPaused(RuntimeError)`
  - `PAUSED_MESSAGE: str` and `CAP_MESSAGE: str`
  - `model_call_refusal() -> str` (`''` means allowed)
  - `run_scope()`, a context manager
  - `guard_model_call(fn) -> fn`
  - `record_model_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None`
  - `core.agents.models.ModelUsageDay(day: date, model: str, prompt_tokens: int, completion_tokens: int)`
  - `plugins.installed.ai_assistant.services.llm.AIPaused` stays importable and is the same class.

**Ruling carried from planning.** The spec says `AgentRuntime.run` enters `run_scope()`. This plan wraps only the runtime's own two provider calls instead, because a tool that calls a model during a run (for example `content.draft_product_description`) is spend that `AgentRun` never records. That call must be checked and counted like any other. Calls inside the scope are still neither re-checked nor re-counted, which is what the spec asks for.

- [ ] **Step 1: Write the failing test**

Create `core/agents/tests/test_provider_guard.py`:

```python
"""Every model call through a core provider obeys the merchant's guardrails.

Six callers reached `provider.respond()` directly — page help, the brain
analyst, the morning briefing, dynamics autopilot, self-improvement, the
dashboard's description fill — with the kill switch off and outside the spend
cap. The guard now sits on the provider class itself; calls made outside the
agent runtime's own loop are counted in ModelUsageDay so the cap sees them.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents import guardrails
from core.agents.llm import FallbackProviderRouter, LLMResponse, LLMToolCall, MockLLMProvider
from core.agents.models import ModelUsageDay
from core.agents.runtime import AgentRuntime
from core.agents.tests.test_runtime import _agent, _tool


def _set(**kw):
    from plugins.registry import app_registry

    plugin = app_registry.get('agent_core')
    for k, v in kw.items():
        plugin.set_config(k, v)


def _resp(pt=0, ct=0, text='x'):
    return LLMResponse(text=text, prompt_tokens=pt, completion_tokens=ct, model='gpt-4o')


class GuardTests(TestCase):
    def setUp(self):
        self.addCleanup(_set, agents_paused=False, spend_cap_daily=0)

    def test_switched_off_ai_makes_no_call(self):
        _set(agents_paused=True)
        provider = MockLLMProvider([_resp()])
        with self.assertRaises(guardrails.AIPaused) as cm:
            provider.respond(messages=[])
        self.assertEqual(str(cm.exception), guardrails.PAUSED_MESSAGE)
        self.assertEqual(provider.calls, [])

    def test_a_reached_spend_cap_makes_no_call(self):
        _set(spend_cap_daily=1.0)
        ModelUsageDay.objects.create(
            day=guardrails.today_start().date(), model='gpt-4o', prompt_tokens=1_000_000
        )
        provider = MockLLMProvider([_resp()])
        with self.assertRaises(guardrails.AIPaused) as cm:
            provider.respond(messages=[])
        self.assertEqual(str(cm.exception), guardrails.CAP_MESSAGE)

    def test_the_ai_assistant_name_is_the_same_class(self):
        from plugins.installed.ai_assistant.services.llm import AIPaused

        self.assertIs(AIPaused, guardrails.AIPaused)


class UsageTests(TestCase):
    def _usage(self):
        return {
            (r.model, r.prompt_tokens, r.completion_tokens) for r in ModelUsageDay.objects.all()
        }

    def test_a_call_outside_a_run_is_counted(self):
        MockLLMProvider([_resp(100, 20), _resp(1, 2)]).respond(messages=[])
        self.assertEqual(self._usage(), {('gpt-4o', 100, 20)})

    def test_calls_accumulate_on_one_row(self):
        provider = MockLLMProvider([_resp(100, 20), _resp(1, 2)])
        provider.respond(messages=[])
        provider.respond(messages=[])
        self.assertEqual(self._usage(), {('gpt-4o', 101, 22)})

    def test_the_fallback_router_counts_its_call_once(self):
        router = FallbackProviderRouter(MockLLMProvider([_resp(50, 5)]), [])
        router.respond(messages=[])
        self.assertEqual(self._usage(), {('gpt-4o', 50, 5)})

    def test_counted_usage_reaches_the_spend_cap(self):
        MockLLMProvider([_resp(1_000_000, 0)]).respond(messages=[])
        self.assertGreater(guardrails.daily_spend_usd(), 2.0)

    def test_a_row_made_by_another_worker_is_added_to_not_lost(self):
        # Review Focus 2: the row already exists when this worker records.
        ModelUsageDay.objects.create(
            day=guardrails.today_start().date(), model='gpt-4o', prompt_tokens=10
        )
        guardrails.record_model_usage('gpt-4o', 5, 1)
        self.assertEqual(self._usage(), {('gpt-4o', 15, 1)})

    def test_a_runs_own_calls_are_not_counted_twice(self):
        agent = _agent(tools=[_tool()], max_steps=3)
        provider = MockLLMProvider([_resp(70, 7, text='done')])
        res = AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(res.state, 'completed')
        self.assertEqual(ModelUsageDay.objects.count(), 0)

    def test_a_model_call_made_by_a_tool_inside_a_run_is_counted(self):
        def handler(**_):
            MockLLMProvider([_resp(9, 3)]).respond(messages=[])
            return {'ok': True}

        agent = _agent(tools=[_tool(handler=handler)], max_steps=3)
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c', name='do_thing', arguments={})]),
                _resp(text='done'),
            ]
        )
        AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(self._usage(), {('gpt-4o', 9, 3)})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST core.agents.tests.test_provider_guard`
Expected: ERROR, `ImportError: cannot import name 'ModelUsageDay' from 'core.agents.models'`.

- [ ] **Step 3: Add the model (`core/agents/models.py`, append)**

```python


class ModelUsageDay(models.Model):
    """Tokens one model spent today outside the agent runtime's own calls.

    The dashboard's description fill, page help, the brain analyst, autopilot,
    self-improvement and tools that call a model reach providers directly; the
    spend cap (core/agents/guardrails.py) adds these rows to the runs' and
    Linda's totals. One row per (day, model), incremented in place.
    """

    day = models.DateField()
    model = models.CharField(max_length=100, blank=True)
    prompt_tokens = models.BigIntegerField(default=0)
    completion_tokens = models.BigIntegerField(default=0)

    class Meta:
        app_label = 'core'
        constraints = [
            models.UniqueConstraint(fields=['day', 'model'], name='core_modelusageday_day_model')
        ]

    def __str__(self) -> str:  # pragma: no cover — debug only
        return f'{self.day} {self.model}: {self.prompt_tokens}+{self.completion_tokens}'
```

Add `ModelUsageDay` to the `from core.agents.models import (…)` re-export in `core/models.py` (~line 321).

Run: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations core -n modelusageday`
Expected: `core/migrations/0023_modelusageday.py` containing `CreateModel` for `ModelUsageDay`.

- [ ] **Step 4: Add the guard to `core/agents/guardrails.py`**

Change the imports at the top of the module to:

```python
from __future__ import annotations

import contextlib
import contextvars
import functools
import logging
from datetime import datetime

logger = logging.getLogger('morpheus.agents.guardrails')

# Shown to the merchant verbatim (dashboard buttons, Linda, background logs).
PAUSED_MESSAGE = 'AI is paused in Settings → Agent guardrails.'
CAP_MESSAGE = "AI has reached today's spend limit set in Agent guardrails."


class AIPaused(RuntimeError):
    """The merchant's agent guardrails refuse this call: AI is switched off, or
    today's spend cap is reached. The message is fit to show the merchant."""
```

Append at the end of the module:

```python


# ── The provider-level guard (v0.113.0) ───────────────────────────────────────


def model_call_refusal() -> str:
    """Why a model call must not run now, or '' to allow. The run cap is left
    out: a button click or a nightly analysis is not an agent run."""
    if agents_paused():
        return PAUSED_MESSAGE
    cap = daily_spend_cap_usd()
    if cap and daily_spend_usd() >= cap:
        return CAP_MESSAGE
    return ''


# True while a call is already accounted for: inside the runtime's own provider
# call (the run checked its caps and stores its tokens on the AgentRun), or
# inside an outer guarded call (the fallback router calling a provider).
_accounted = contextvars.ContextVar('guardrails_accounted', default=False)


@contextlib.contextmanager
def run_scope():
    """Wrap the agent runtime's OWN provider calls. A model call a tool makes
    during the run is not inside this scope, so it is checked and counted."""
    token = _accounted.set(True)
    try:
        yield
    finally:
        _accounted.reset(token)


def guard_model_call(respond):
    """Wrap a provider's ``respond``: refuse when the guardrails say so, and
    record the tokens of a call nothing else accounts for."""

    @functools.wraps(respond)
    def wrapper(self, *args, **kwargs):
        if _accounted.get():
            return respond(self, *args, **kwargs)
        reason = model_call_refusal()
        if reason:
            raise AIPaused(reason)
        token = _accounted.set(True)
        try:
            resp = respond(self, *args, **kwargs)
        finally:
            _accounted.reset(token)
        record_model_usage(
            getattr(resp, 'model', '') or getattr(self, 'model', '') or '',
            getattr(resp, 'prompt_tokens', 0),
            getattr(resp, 'completion_tokens', 0),
        )
        return resp

    return wrapper


def record_model_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Add a call's tokens to today's row for its model. Never raises: losing a
    count is better than failing the call it describes."""
    pt, ct = int(prompt_tokens or 0), int(completion_tokens or 0)
    if not (pt or ct):
        return
    try:
        from django.db import IntegrityError, transaction
        from django.db.models import F

        from core.agents.models import ModelUsageDay

        day, name = today_start().date(), (model or '')[:100]

        def _add() -> int:
            return ModelUsageDay.objects.filter(day=day, model=name).update(
                prompt_tokens=F('prompt_tokens') + pt,
                completion_tokens=F('completion_tokens') + ct,
            )

        # Own savepoint: a failure here must not abort the caller's transaction.
        with transaction.atomic():
            if _add():
                return
            try:
                with transaction.atomic():
                    ModelUsageDay.objects.create(
                        day=day, model=name, prompt_tokens=pt, completion_tokens=ct
                    )
            except IntegrityError:  # another worker created today's row first
                _add()
    except Exception:  # noqa: BLE001
        logger.warning('guardrails: could not record model usage', exc_info=True)


def _outside_run_usage_today() -> list[dict]:
    try:
        from core.agents.models import ModelUsageDay

        return [
            {'model': r.model, 'pt': r.prompt_tokens, 'ct': r.completion_tokens}
            for r in ModelUsageDay.objects.filter(day=today_start().date())
        ]
    except Exception:  # noqa: BLE001 — a missing table must not lift the cap
        return []
```

In `daily_spend_usd`, after `rows += _app_usage_today()`, add `rows += _outside_run_usage_today()`.

- [ ] **Step 5: Wrap every provider (`core/agents/llm.py`)**

Inside `class LLMProvider(ABC):`, after `model: str = ''`, add:

```python

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Every provider's respond obeys the merchant's guardrails and reports
        # what it spent: six callers once reached a model here directly, with
        # the kill switch off and outside the spend cap (v0.113.0).
        if 'respond' in cls.__dict__:
            from core.agents.guardrails import guard_model_call

            cls.respond = guard_model_call(cls.__dict__['respond'])
```

- [ ] **Step 6: Mark the runtime's own calls (`core/agents/runtime.py`)**

Add `run_scope` to the existing import: `from core.agents.guardrails import agents_paused, run_scope, run_start_block_reason`.

In `run()`, change

```python
            try:
                response = self.provider.respond(
                    messages=messages,
                    tools=tools,
                    temperature=self.agent.temperature,
                    max_tokens=self.agent.max_tokens,
                )
```

to

```python
            try:
                with run_scope():  # checked at run start; tokens stored on the AgentRun
                    response = self.provider.respond(
                        messages=messages,
                        tools=tools,
                        temperature=self.agent.temperature,
                        max_tokens=self.agent.max_tokens,
                    )
```

In `_summarize_history`, change `resp = self.provider.respond(` to

```python
        with run_scope():
            resp = self.provider.respond(
```

and re-indent its arguments and closing `)` one level.

- [ ] **Step 7: One `AIPaused` class (`plugins/installed/ai_assistant/services/llm.py`)**

Delete the local `class AIPaused(RuntimeError): …` block. Replace the body of `guardrail_refusal()`, below its docstring, with:

```python
    from core.agents import guardrails

    return guardrails.model_call_refusal()
```

Add at module top, with the other imports:

```python
from core.agents.guardrails import AIPaused  # noqa: F401 — callers import it from here
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `$TEST core.agents core.assistant plugins.installed.ai_assistant plugins.installed.ai_content plugins.installed.agent_core`
Expected: OK. If a test uses `assertNumQueries` around a provider call made outside a run, the guard's config read and usage write add queries. Raise that count by the measured difference and ledger it.

Run: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 9: Commit**

```bash
git add core/agents/guardrails.py core/agents/models.py core/models.py core/agents/llm.py core/agents/runtime.py core/migrations/0023_modelusageday.py plugins/installed/ai_assistant/services/llm.py core/agents/tests/test_provider_guard.py
git commit -m "fix(ai): every provider call obeys the kill switch and spend cap, and is counted

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: The six direct callers say why when AI is paused

**Files:**
- Modify:
  - `core/assistant/page_help.py` (an `except AIPaused` before the generic `except`, ~line 77)
  - `plugins/installed/admin_dashboard/views_split/products.py` (`content_fill_one`: refuse up front, ~line 1004)
- Test:
  - `core/agents/tests/test_direct_callers_paused.py` (core callers)
  - `plugins/tests_ai_paused_callers.py` (app callers)

**Interfaces:**
- Consumes: `guardrails.AIPaused`, `PAUSED_MESSAGE`, `model_call_refusal()` (Task 6).
- Produces: none.

- [ ] **Step 1: Write the failing tests**

Create `core/agents/tests/test_direct_callers_paused.py`:

```python
"""Core's direct model callers stop when AI is switched off, without a 500.

Each used to reach the provider with the switch off. They now meet the
provider guard (test_provider_guard) and each turns the refusal into its own
quiet failure; page help shows the merchant the reason.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.agents import guardrails
from core.agents.llm import LLMProvider, LLMResponse


class _Probe(LLMProvider):
    name = 'probe'
    model = 'gpt-4o'

    def __init__(self):
        self.calls = 0

    def respond(self, **_kw):
        self.calls += 1
        return LLMResponse(text='{}', model='gpt-4o')


def _pause():
    from plugins.registry import app_registry

    p = app_registry.get('agent_core')
    p.set_config('agents_paused', True)
    return p


class CoreCallersPausedTests(TestCase):
    def setUp(self):
        p = _pause()
        self.addCleanup(p.set_config, 'agents_paused', False)
        self.probe = _Probe()
        patcher = patch('core.agents.llm.get_llm_provider', return_value=self.probe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_page_help_names_the_reason(self):
        from core.assistant.page_help import build_page_help

        out = build_page_help({'page_text': 'x' * 400}, provider=self.probe)
        self.assertFalse(out['ok'])
        self.assertEqual(out['message'], guardrails.PAUSED_MESSAGE)
        self.assertEqual(self.probe.calls, 0)

    def test_the_brain_analyst_reports_the_refusal(self):
        from core.brain.analyst import analyze

        out = analyze(signals={})
        self.assertIn('paused', out.get('error', ''))
        self.assertEqual(self.probe.calls, 0)

    def test_self_improvement_falls_back_without_calling(self):
        from core.self_improvement.verify import verify_recommendation

        result = verify_recommendation({'title': 't'})
        self.assertIsNotNone(result)
        self.assertEqual(self.probe.calls, 0)
```

Create `plugins/tests_ai_paused_callers.py`:

```python
"""The apps' direct model callers stop when AI is switched off, without a 500."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents import guardrails
from core.agents.llm import LLMProvider, LLMResponse
from plugins.installed.catalog.models import Product


class _Probe(LLMProvider):
    name = 'probe'
    model = 'gpt-4o'

    def __init__(self):
        self.calls = 0

    def respond(self, **_kw):
        self.calls += 1
        return LLMResponse(text='[]', model='gpt-4o')


class AppCallersPausedTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)
        self.probe = _Probe()
        patcher = patch('core.agents.llm.get_llm_provider', return_value=self.probe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_description_fill_says_ai_is_paused(self):
        staff = get_user_model().objects.create_user(
            username='fill', email='f@x.test', password='x', is_staff=True
        )
        self.client.force_login(staff)
        p = Product.objects.create(name='Fill', slug='fill-paused', sku='FP', price=Money(1, 'USD'))
        resp = self.client.post(f'/dashboard/products/{p.pk}/content-fill/')
        self.assertEqual(resp.json(), {'ok': False, 'error': guardrails.PAUSED_MESSAGE})
        self.assertEqual(self.probe.calls, 0)

    def test_the_morning_briefing_reports_the_refusal(self):
        from plugins.installed.morpheus_brain.services import generate_briefing

        out = generate_briefing()
        self.assertIn('paused', out.get('error', ''))
        self.assertEqual(self.probe.calls, 0)

    def test_autopilot_keeps_its_templates(self):
        from plugins.installed.dynamics.autopilot import _enrich_with_llm

        drafts = [{'title': 'Keep me', 'rationale': 'because'}]
        _enrich_with_llm(drafts)
        self.assertEqual(drafts[0]['title'], 'Keep me')
        self.assertEqual(self.probe.calls, 0)

    def test_the_draft_tool_returns_an_error_to_the_agent(self):
        from core.agents.tools import ToolError
        from plugins.installed.agent_core.tools import content

        Product.objects.create(name='Draft', slug='draft-paused', sku='DP', price=Money(1, 'USD'))
        with (
            patch.object(content, 'get_llm_provider', return_value=self.probe),
            self.assertRaises(ToolError) as cm,
        ):
            content.draft_product_description_tool.invoke({'slug': 'draft-paused'})
        self.assertIn('paused', str(cm.exception))
```

(The test client's `force_login` is for the local test DB only. The rule against `force_login` applies to production checks.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$TEST core.agents.tests.test_direct_callers_paused plugins.tests_ai_paused_callers`
Expected: FAIL.
- `test_page_help_names_the_reason` fails with `'Linda is unavailable right now.' != 'AI is paused…'`.
- `test_description_fill_says_ai_is_paused` fails with `{'ok': True, …} != …`.

The other tests should already pass, because the guard from Task 6 refuses and the callers' existing excepts absorb the refusal. Ledger that as expected.

- [ ] **Step 3: Page help names the reason (`core/assistant/page_help.py`)**

Directly before `except Exception as e:  # noqa: BLE001 — provider/breaker safety net`, insert:

```python
    except AIPaused as e:  # the merchant switched AI off or hit today's cap: say so
        return {**fail, 'message': str(e)}
```

Then, in the function body before the `try:`, add `from core.agents.guardrails import AIPaused`, right after the `from core.agents.llm import LLMMessage` line.

- [ ] **Step 4: Description fill refuses up front (`admin_dashboard/views_split/products.py`)**

In `content_fill_one`, directly after `p = get_object_or_404(Product, pk=product_id)`, add:

```python
    from core.agents.guardrails import model_call_refusal

    # The merchant's guardrails: say why instead of "no changes" (the content
    # audit page shows `error`).
    refusal = model_call_refusal()
    if refusal:
        return JsonResponse({'ok': False, 'error': refusal}, status=503)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$TEST core.agents.tests.test_direct_callers_paused plugins.tests_ai_paused_callers core.assistant plugins.installed.admin_dashboard`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add core/assistant/page_help.py plugins/installed/admin_dashboard/views_split/products.py core/agents/tests/test_direct_callers_paused.py plugins/tests_ai_paused_callers.py
git commit -m "fix(ai): page help and description fill say AI is paused instead of failing vaguely

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Embeddings, gateway embeds and text-to-speech obey the kill switch; `agent_mcp` is protected

**Files:**
- Modify:
  - `core/embeddings.py` (inside the `if provider == 'openai' and …:` branch of `embed`)
  - `plugins/installed/ai_assistant/services/llm.py` (`LLMGateway.__init_subclass__` also wraps `embed`)
  - `plugins/installed/audiobooks/services.py` (`_tts`)
  - `core/safety.py` (`PROTECTED_PLUGINS`)
  - `plugins/installed/admin_dashboard/tests/test_disable_guards.py` (add `'agent_mcp'` to the tuple in `test_no_surface_can_disable_a_soft_bricking_app`)
- Test:
  - `core/tests/test_embeddings_paused.py`
  - `plugins/installed/ai_assistant/tests/test_guarded_gateway.py` (one test added)
  - `plugins/installed/audiobooks/tests/test_tts_paused.py`

**Interfaces:**
- Consumes: `guardrails.agents_paused()`, `AIPaused`, `PAUSED_MESSAGE` (Task 6).
- Produces: `is_plugin_protected('agent_mcp') is True`.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_embeddings_paused.py`:

```python
"""With AI switched off, embeddings use the hash fallback instead of OpenAI."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from core import embeddings


class EmbeddingsPausedTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)

    @override_settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-test')
    def test_no_openai_call_and_the_hash_vector_comes_back(self):
        with patch('openai.OpenAI') as client:
            vec = embeddings.embed('kayak kotor')
        client.assert_not_called()
        self.assertEqual(vec, embeddings._hash_embedding('kayak kotor'))
```

Append to `plugins/installed/ai_assistant/tests/test_guarded_gateway.py`, inside `GuardedGatewayTests`:

```python
    def test_switched_off_ai_makes_no_embedding_call(self):
        _set(agents_paused=True)
        gw = _gateway()
        with self.assertRaises(AIPaused):
            gw.embed('text')
        gw.client.embeddings.create.assert_not_called()
```

Create `plugins/installed/audiobooks/tests/test_tts_paused.py`:

```python
"""With AI switched off, no ElevenLabs call is made."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.agents.guardrails import PAUSED_MESSAGE, AIPaused
from plugins.installed.audiobooks.services import _tts


class TtsPausedTests(TestCase):
    def test_no_request_while_paused(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)
        with patch('requests.post') as post, self.assertRaises(AIPaused) as cm:
            _tts('hello', api_key='k', voice_id='v', model='m')
        post.assert_not_called()
        self.assertEqual(str(cm.exception), PAUSED_MESSAGE)
```

Add `'agent_mcp',` to the tuple of names in `ProtectedAppGuardTests.test_no_surface_can_disable_a_soft_bricking_app` (`plugins/installed/admin_dashboard/tests/test_disable_guards.py`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$TEST core.tests.test_embeddings_paused plugins.installed.ai_assistant.tests.test_guarded_gateway plugins.installed.audiobooks.tests.test_tts_paused plugins.installed.admin_dashboard.tests.test_disable_guards`
Expected: FAIL.
- The embeddings test fails with `Expected 'OpenAI' to not have been called`.
- The gateway embed test fails with `AIPaused not raised`.
- The TTS test fails with `AIPaused not raised`.
- The protected-app test fails with `agent_mcp: AI disable tools would allow it`.

- [ ] **Step 3: Embeddings (`core/embeddings.py`)**

Directly inside `if provider == 'openai' and getattr(settings, 'OPENAI_API_KEY', ''):`, before its `try:`, insert:

```python
        from core.agents.guardrails import agents_paused

        if agents_paused():
            # AI is switched off: no provider call; the hash vector keeps
            # retrieval working, the documented degrade path below.
            return _hash_embedding(text)
```

- [ ] **Step 4: Gateway embeds (`plugins/installed/ai_assistant/services/llm.py`)**

Below `_guarded`, add:

```python
def _paused_guard(embed):
    """Embeddings cost little and are not priced, so only the kill switch applies."""

    @functools.wraps(embed)
    def wrapper(self, *args, **kwargs):
        from core.agents import guardrails

        if guardrails.agents_paused():
            raise AIPaused(guardrails.PAUSED_MESSAGE)
        return embed(self, *args, **kwargs)

    return wrapper
```

In `LLMGateway.__init_subclass__`, after the `complete` wrap, add:

```python
        if 'embed' in cls.__dict__:
            cls.embed = _paused_guard(cls.__dict__['embed'])
```

- [ ] **Step 5: Text-to-speech (`plugins/installed/audiobooks/services.py`)**

At the top of `_tts`, before `import requests`, insert:

```python
    from core.agents.guardrails import PAUSED_MESSAGE, AIPaused, agents_paused

    if agents_paused():
        raise AIPaused(PAUSED_MESSAGE)  # generate() records the failure on the audiobook
```

- [ ] **Step 6: Protect `agent_mcp` (`core/safety.py`)**

In `PROTECTED_PLUGINS`, after `'agent_core',`, add:

```python
    # Every Linda turn reaches the store's tools through /mcp/admin/v1/; disable
    # agent_mcp and she answers with no tools at all.
    'agent_mcp',
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `$TEST core.tests.test_embeddings_paused plugins.installed.ai_assistant plugins.installed.audiobooks plugins.installed.admin_dashboard.tests.test_disable_guards core.tests`
Expected: OK.

- [ ] **Step 8: Commit**

```bash
git add core/embeddings.py plugins/installed/ai_assistant/services/llm.py plugins/installed/audiobooks/services.py core/safety.py core/tests/test_embeddings_paused.py plugins/installed/ai_assistant/tests/test_guarded_gateway.py plugins/installed/audiobooks/tests/test_tts_paused.py plugins/installed/admin_dashboard/tests/test_disable_guards.py
git commit -m "fix(ai): embeddings and text-to-speech obey the kill switch; agent_mcp is protected

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: No session for visitors; no environments middleware; expired sessions cleared

**Files:**
- Modify:
  - `plugins/installed/ai_assistant/middleware.py`. Delete `AIContext.memories`, `AIContext.ab_cohort`, `get_memory_context_string`, `_attach_customer_memories`, the `self._attach_customer_memories(ctx, user)` call, the whole `if hasattr(request, 'session'):` block, and the `random` and `string` imports.
  - `morph/settings.py` (delete the `'plugins.installed.environments.middleware.EnvironmentMiddleware',` line)
  - `core/tasks.py` (new `clear_expired_sessions` task)
  - `morph/celery.py` (`_CORE_BEAT_SCHEDULE` entry `core-clear-sessions`)
  - `core/tests/test_beat_schedule.py` (add `'core-clear-sessions'` to `CORE_JOBS`)
  - `plugins/installed/dynamics/app.py` and `plugins/installed/advanced_ecommerce/app.py`: `on_product_viewed` skips crawlers. A probe run during planning found these two still writing `session['recently_viewed']` on every product-page hit, crawlers included, after `ab_cohort`.
- Test:
  - `plugins/installed/storefront/tests/test_no_session_for_visitors.py`
  - `core/tests/test_clear_sessions.py`

**Interfaces:**
- Produces:
  - Celery task `core.tasks.clear_expired_sessions`, registered under that name.
  - Beat key `core-clear-sessions`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/storefront/tests/test_no_session_for_visitors.py`:

```python
"""A visitor's GET writes no session and sets no session cookie.

ai_assistant's middleware wrote `session['ab_cohort']`, which nothing read, on
every request: with database sessions that was an INSERT plus `Set-Cookie:
sessionid` per crawler hit, and the cookie took the visitor's later pages out
of the edge cache (`sessionid` is a private cookie in storefront/middleware.py).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product

_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
_CRAWLER = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'


class NoSessionForVisitorsTests(TestCase):
    def setUp(self):
        Product.objects.create(
            name='Visit', slug='visit-probe', sku='VIS', price=Money(Decimal('3'), 'USD'),
            product_type='simple', status='active',
        )

    def test_the_home_page_sets_no_session_cookie(self):
        resp = self.client.get('/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, resp.cookies)
        self.assertEqual(Session.objects.count(), 0)

    def test_a_crawler_on_a_product_page_gets_no_session(self):
        # Review Focus 5. dynamics and advanced_ecommerce kept a recently-viewed
        # list for every product hit, crawlers included (~9 in 10 hits).
        resp = self.client.get('/products/visit-probe/', HTTP_USER_AGENT=_CRAWLER)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, resp.cookies)
        self.assertEqual(Session.objects.count(), 0)

    def test_a_shopper_still_gets_a_recently_viewed_list(self):
        self.client.get('/products/visit-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(self.client.session.get('recently_viewed'), ['visit-probe'])

    def test_the_environments_middleware_is_not_in_the_stack(self):
        self.assertNotIn(
            'plugins.installed.environments.middleware.EnvironmentMiddleware',
            settings.MIDDLEWARE,
        )
```

Create `core/tests/test_clear_sessions.py`:

```python
"""Expired sessions are cleared daily (nothing ever ran clearsessions)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone

from core.tasks import clear_expired_sessions


class ClearExpiredSessionsTests(TestCase):
    def test_expired_rows_go_and_live_ones_stay(self):
        live = SessionStore()
        live.create()
        old = SessionStore()
        old.create()
        Session.objects.filter(session_key=old.session_key).update(
            expire_date=timezone.now() - timedelta(days=1)
        )
        clear_expired_sessions()
        self.assertEqual(
            list(Session.objects.values_list('session_key', flat=True)), [live.session_key]
        )

    def test_it_is_registered_under_its_name(self):
        self.assertEqual(clear_expired_sessions.name, 'core.tasks.clear_expired_sessions')
```

In `core/tests/test_beat_schedule.py`, add `'core-clear-sessions',` to `CORE_JOBS`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$TEST plugins.installed.storefront.tests.test_no_session_for_visitors core.tests.test_clear_sessions core.tests.test_beat_schedule`
Expected:
- `test_the_home_page_sets_no_session_cookie` and `test_a_crawler_on_a_product_page_gets_no_session` FAIL with `'sessionid' unexpectedly found`.
- The recently-viewed test passes; it already works and must keep working.
- The middleware test FAILs.
- `test_clear_sessions` errors with `ImportError: cannot import name 'clear_expired_sessions'`.
- The beat test FAILs on `core-clear-sessions`.

- [ ] **Step 3: Strip the unused work from `AIContextMiddleware`**

In `plugins/installed/ai_assistant/middleware.py`:
- Delete `import random` and `import string`.
- Delete the dataclass fields `memories: list[dict] = field(default_factory=list)` and `ab_cohort: str = ''`.
- Delete `get_memory_context_string`.
- Delete `_attach_customer_memories`.
- In `_build_context`, delete `self._attach_customer_memories(ctx, user)` and the whole block

```python
        if hasattr(request, 'session'):
            ctx.ab_cohort = request.session.get('ab_cohort', '')
            if not ctx.ab_cohort:
                ctx.ab_cohort = ''.join(random.choices(string.ascii_lowercase, k=8))  # noqa: S311
                request.session['ab_cohort'] = ctx.ab_cohort
```

Update the module docstring's second line to:
`Attaches an AIContext (agent capabilities, customer id) to every request.`

Then run `grep -rn "ab_cohort\|get_memory_context_string\|\.memories\b" --include='*.py' plugins core api`. The expected output is empty; any hit is a reader the explorer missed, so stop and reassess.

- [ ] **Step 3b: Crawlers get no recently-viewed list**

In both `plugins/installed/dynamics/app.py` and `plugins/installed/advanced_ecommerce/app.py`, change the first guard of `on_product_viewed` from

```python
        if request is None or product is None:
            return
```

to

```python
        if request is None or product is None:
            return
        from core.utils.crawlers import is_crawler_user_agent

        # A crawler has no use for a recently-viewed list, and writing one gave
        # every crawled product page a database session and a cookie.
        if is_crawler_user_agent(request.META.get('HTTP_USER_AGENT')):
            return
```

- [ ] **Step 4: Remove the environments middleware**

In `morph/settings.py`, delete the line `'plugins.installed.environments.middleware.EnvironmentMiddleware',` from `MIDDLEWARE`.

- [ ] **Step 5: Add the clear task (`core/tasks.py`, after `check_for_updates`)**

```python


@shared_task(name='core.tasks.clear_expired_sessions', time_limit=300, soft_time_limit=240)
def clear_expired_sessions() -> None:
    """Delete expired sessions (database-backed). Nothing ever ran Django's
    `clearsessions`, so every store kept a row per crawler hit for months."""
    from importlib import import_module

    from django.conf import settings

    import_module(settings.SESSION_ENGINE).SessionStore.clear_expired()
```

In `morph/celery.py`, add to `_CORE_BEAT_SCHEDULE`, after the `core-check-for-updates` entry:

```python
    # Expired sessions are deleted daily: database sessions are never removed
    # otherwise, and every store had a row per crawler hit until v0.113.0.
    'core-clear-sessions': {
        'task': 'core.tasks.clear_expired_sessions',
        'schedule': crontab(hour=4, minute=15),  # 04:15 UTC daily
    },
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `$TEST plugins.installed.storefront.tests.test_no_session_for_visitors core.tests.test_clear_sessions core.tests.test_beat_schedule core.tests.test_celery_wiring plugins.installed.ai_assistant plugins.installed.environments plugins.installed.dynamics plugins.installed.advanced_ecommerce`
Expected: OK. If an existing dynamics or advanced_ecommerce test drives a product view with the test client's default empty user agent and expects `recently_viewed`, give it a browser UA and ledger the change. An empty UA counts as "not a browser" (`core/utils/crawlers.py`).

If the cookie test still finds `sessionid`, another writer remains. Patch `SessionBase.__setitem__` with a spy that records `traceback.format_stack()`, rerun the test once, and read which module wrote. Remove that write only if nothing reads the key; otherwise stop and report. Ledger either outcome.

- [ ] **Step 7: Commit**

```bash
git add plugins/installed/ai_assistant/middleware.py morph/settings.py core/tasks.py morph/celery.py core/tests/test_beat_schedule.py core/tests/test_clear_sessions.py plugins/installed/storefront/tests/test_no_session_for_visitors.py plugins/installed/dynamics/app.py plugins/installed/advanced_ecommerce/app.py
git commit -m "perf: visitors no longer cost a session write; environments middleware out; daily clearsessions

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: One webhook trigger, one POST, one body shape

**Files:**
- Modify:
  - `core/hooks.py`: add `WEBHOOK_DELIVER` beside the Task 1 constants. `_dispatch_remote` defers to a new `_deliver_one`. `WebhookEncoder` adds identifying fields to model instances.
  - `core/tasks.py`: `dispatch_webhook` posts through `core.net.outbound_request` (Task 12 adds that helper; until then keep `requests.post` and add `allow_redirects=False`).
  - `plugins/installed/webhooks_ui/app.py`: delete `_FANOUT_EVENTS`, `_flatten`, `_make_fanout` and `_fanout`, and register a `WEBHOOK_DELIVER` answer.
  - `plugins/installed/webhooks_ui/services.py`: `build_signed_request_body` returns core's canonical body.
  - `plugins/installed/webhooks_ui/tasks.py`: add `allow_redirects=False` to `requests.post`.
  - `core/tests_webhook_on_commit.py`: the core-path test runs with webhooks_ui off.
- Test: `plugins/installed/webhooks_ui/tests/test_one_trigger.py`

**Interfaces:**
- Produces:
  - `MorpheusEvents.WEBHOOK_DELIVER = 'webhook.deliver'`, a filter with value `False` and kwargs `endpoint`, `event_name`, `payload`.
  - `HookRegistry._deliver_one(endpoint, event_name: str, payload: dict) -> None`.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/webhooks_ui/tests/test_one_trigger.py`:

```python
"""A merchant webhook is posted once, after commit, in one body shape.

Core's dispatcher and webhooks_ui's fan-out both posted every subscribed event,
in two shapes; the fan-out enqueued during the hook, so it could post before the
transaction committed, or for one that rolled back, and it ignored '*'. Core is
now the only trigger; webhooks_ui takes the delivery (log, retries, replay)
through the WEBHOOK_DELIVER filter.
"""

from __future__ import annotations

import json
from unittest import mock

from django.db import transaction
from django.test import TestCase

from core.hooks import hook_registry
from core.models import WebhookEndpoint
from core.tasks import _canonical_payload
from plugins.installed.webhooks_ui.models import WebhookDelivery
from plugins.installed.webhooks_ui.tasks import deliver_webhook
from plugins.registry import app_registry

_UI = 'plugins.installed.webhooks_ui.tasks.deliver_webhook.delay'
_CORE = 'core.tasks.dispatch_webhook.delay'
# An event no app subscribes to: the test exercises delivery, not order handlers.
EVENT = 'test.webhook.event'


def _endpoint(events):
    return WebhookEndpoint.objects.create(
        name='t', url='https://example.com/hook', secret='s', events=events, is_active=True
    )


class OneTriggerTests(TestCase):
    def test_one_delivery_through_webhooks_ui_and_none_from_core(self):
        _endpoint([EVENT])
        with mock.patch(_UI) as ui, mock.patch(_CORE) as core:
            with self.captureOnCommitCallbacks(execute=True):
                hook_registry.fire(EVENT, foo='bar')
        self.assertEqual(ui.call_count, 1)
        core.assert_not_called()
        self.assertEqual(WebhookDelivery.objects.get().payload, {'foo': 'bar'})

    def test_nothing_is_sent_when_the_transaction_rolls_back(self):
        _endpoint([EVENT])
        with mock.patch(_UI) as ui, mock.patch(_CORE) as core:
            try:
                with transaction.atomic():
                    hook_registry.fire(EVENT, foo='bar')
                    raise RuntimeError('rollback')
            except RuntimeError:
                pass
        ui.assert_not_called()
        core.assert_not_called()
        self.assertFalse(WebhookDelivery.objects.exists())

    def test_an_all_events_endpoint_reaches_the_log(self):
        _endpoint(['*'])
        with mock.patch(_UI), self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire('test.webhook.other', foo=1)
        self.assertEqual(WebhookDelivery.objects.get().event_name, 'test.webhook.other')

    def test_with_webhooks_ui_off_core_posts_once(self):
        self.addCleanup(app_registry.activate, 'webhooks_ui')
        app_registry.deactivate('webhooks_ui')
        _endpoint([EVENT])
        with mock.patch(_CORE) as core, self.captureOnCommitCallbacks(execute=True):
            hook_registry.fire(EVENT, foo='bar')
        self.assertEqual(core.call_count, 1)

    def test_if_webhooks_ui_cannot_enqueue_core_still_posts(self):
        # Review Focus 3: a broken delivery owner must not lose the event.
        _endpoint([EVENT])
        with (
            mock.patch(
                'plugins.installed.webhooks_ui.services.enqueue_delivery',
                side_effect=RuntimeError('db down'),
            ),
            mock.patch(_CORE) as core,
            self.captureOnCommitCallbacks(execute=True),
        ):
            hook_registry.fire(EVENT, foo='bar')
        self.assertEqual(core.call_count, 1)

    def test_the_body_is_cores_canonical_payload(self):
        ep = _endpoint(['order.placed'])
        d = WebhookDelivery.objects.create(endpoint=ep, event_name='order.placed', payload={'b': 1, 'a': 2})
        with mock.patch('requests.post') as post, mock.patch('core.net.is_safe_remote_host', return_value=True):
            post.return_value = mock.Mock(status_code=200, text='ok')
            deliver_webhook(str(d.id))
        self.assertEqual(post.call_args.kwargs['data'], _canonical_payload({'b': 1, 'a': 2}))
        self.assertIs(post.call_args.kwargs['allow_redirects'], False)
        self.assertEqual(json.loads(post.call_args.kwargs['data']), {'a': 2, 'b': 1})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.webhooks_ui`
Expected: FAIL.
- `test_one_delivery…` fails because core is called (`core.assert_not_called` fails).
- On sqlite the fan-out's `events__contains` raises and is swallowed, so `ui.call_count` is 0 and the test fails on the count.
- The `*` test fails with `DoesNotExist`.
- The body test fails, comparing `{"data":…,"event":…}` with the bare payload.

- [ ] **Step 3: Add the filter and route core's dispatch through it (`core/hooks.py`)**

After the two consent constants from Task 1, add:

```python
    # WEBHOOK_DELIVER — filter, value=False, kwargs: endpoint (core.WebhookEndpoint),
    #   event_name, payload (JSON-safe dict). Core asks once per subscribed endpoint,
    #   after commit; an app that takes the delivery (webhooks_ui: log, retries,
    #   replay) returns True and core does not post. Nothing answers → core posts.
    WEBHOOK_DELIVER = 'webhook.deliver'  # filter
```

In `_dispatch_remote`, replace

```python
                    transaction.on_commit(
                        lambda url=endpoint.url, secret=endpoint.secret: dispatch_webhook.delay(
                            url, secret, event, payload
                        )
                    )
```

with

```python
                    transaction.on_commit(
                        lambda ep=endpoint: self._deliver_one(ep, event, payload)
                    )
```

Remove `dispatch_webhook` from that function's import (`from core.tasks import dispatch_webhook`) if nothing else in `_dispatch_remote` uses it. Then add this method to `HookRegistry`, after `_dispatch_remote`:

```python
    def _deliver_one(self, endpoint, event_name: str, payload: dict) -> None:
        """One endpoint, one delivery: a delivery owner (webhooks_ui) takes it
        through WEBHOOK_DELIVER, else core posts. Exactly one path runs."""
        taken = self.filter(
            MorpheusEvents.WEBHOOK_DELIVER,
            False,
            endpoint=endpoint,
            event_name=event_name,
            payload=payload,
        )
        if taken is True:
            return
        from core.tasks import dispatch_webhook

        dispatch_webhook.delay(endpoint.url, endpoint.secret, event_name, payload)
```

The kwarg must be `event_name`, never `event`, because `filter()`'s first parameter is named `event`.

In `WebhookEncoder.default`, replace

```python
                if isinstance(o, models.Model):
                    return {'id': str(o.pk), 'model': o.__class__.__name__}
```

with

```python
                if isinstance(o, models.Model):
                    # The identifying fields a receiver needs, never a record dump.
                    out = {'id': str(o.pk), 'model': o.__class__.__name__}
                    for attr in ('order_number', 'sku', 'email', 'name', 'slug', 'status'):
                        v = getattr(o, attr, None)
                        if isinstance(v, (str, int, float, bool)):
                            out[attr] = v
                    return out
```

- [ ] **Step 4: webhooks_ui takes deliveries instead of fanning out (`plugins/installed/webhooks_ui/app.py`)**

Delete `_FANOUT_EVENTS`, `_flatten`, `_make_fanout`, the `_fanout` staticmethod, and the `for event in _FANOUT_EVENTS:` loop in `ready()`. Add this module-level function:

```python
def _take_delivery(value, endpoint=None, event_name='', payload=None, **_):
    """WEBHOOK_DELIVER: log the delivery and queue it (retries, dead-letter,
    replay). Core decided when and to whom; this only delivers."""
    if value or endpoint is None:
        return value
    from plugins.installed.webhooks_ui.services import enqueue_delivery

    enqueue_delivery(endpoint=endpoint, event_name=event_name, payload=payload or {})
    return True
```

In `ready()`, after `self.register_celery_tasks(...)`, add:

```python
        # Core's dispatcher is the only trigger (after commit, honours '*');
        # this app takes each delivery so the merchant keeps the log and replay.
        self.register_hook(events.WEBHOOK_DELIVER, _take_delivery, priority=50)
```

Update the manifest `description` from "Subscribes to core domain events and fans them out to merchant-registered endpoints." to "Takes each delivery core's dispatcher makes, so every attempt is logged and replayable."

- [ ] **Step 5: One body shape, no redirects**

In `plugins/installed/webhooks_ui/services.py`, replace `build_signed_request_body` with:

```python
def build_signed_request_body(*, event_name: str, payload: dict) -> bytes:
    """Core's body (core.tasks._canonical_payload): the event's payload, the
    event name in the X-Morpheus-Event header — one shape for every receiver."""
    from core.tasks import _canonical_payload

    return _canonical_payload(payload)
```

`json` may now be unused in that module; if ruff flags F401, remove the import. In `plugins/installed/webhooks_ui/tasks.py`, change the post to:
`resp = requests.post(d.endpoint.url, data=body, headers=headers, timeout=10, allow_redirects=False)`.

In `core/tasks.py`'s `dispatch_webhook`, change the post to:
`response = requests.post(url, data=body, headers=headers, timeout=10, allow_redirects=False)`.

- [ ] **Step 6: Keep the core test core-only (`core/tests_webhook_on_commit.py`)**

In `WebhookOnCommitTests`, add:

```python
    def setUp(self):
        # Core's own path: with no delivery owner answering WEBHOOK_DELIVER, core
        # posts (webhooks_ui's path is tested in its app).
        from plugins.registry import app_registry

        self.addCleanup(app_registry.activate, 'webhooks_ui')
        app_registry.deactivate('webhooks_ui')
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `$TEST plugins.installed.webhooks_ui core.tests_webhook_on_commit core.tests.test_hook_payload_files core.tests.test_hooks_filter`
Expected: OK.

- [ ] **Step 8: Commit**

```bash
git add core/hooks.py core/tasks.py plugins/installed/webhooks_ui core/tests_webhook_on_commit.py
git commit -m "fix(webhooks): one trigger, one POST after commit, one body shape (wave 0 item 10)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Attribution reports one 30-day total, and Meta's traffic meets Meta's spend

**Files:**
- Modify: `plugins/installed/analytics/services_attribution.py` (`_channel_of`, `roas_by_channel`)
- Test: `plugins/installed/analytics/tests/test_attribution.py` (add `RoasWindowTests`)

**Interfaces:**
- Produces: `roas_by_channel(model='last_touch', days=30) -> list[dict]` (same signature, new sums).

- [ ] **Step 1: Write the failing test**

Append to `plugins/installed/analytics/tests/test_attribution.py`:

```python
class RoasWindowTests(TestCase):
    """Each daily snapshot is already a trailing 30-day total (spend and
    attributed revenue), so summing 31 of them reported ~31x the truth."""

    def test_thirty_one_daily_snapshots_report_the_total_once(self):
        today = timezone.now().date()
        for back in range(31):
            day = today - timedelta(days=back)
            AdSpendSnapshot.objects.create(day=day, channel='meta', spend=Money(Decimal('300'), 'USD'))
            DailyMetric.objects.create(
                day=day, metric='attribution', dimension='last_touch:meta',
                value_money=Money(Decimal('900'), 'USD'),
            )
        [row] = roas_by_channel(model='last_touch')
        self.assertEqual(row['spend'], Decimal('300'))
        self.assertEqual(row['revenue'], Decimal('900'))
        self.assertEqual(row['roas'], 3)

    def test_facebook_and_instagram_traffic_is_metas(self):
        from types import SimpleNamespace

        from plugins.installed.analytics.services_attribution import _channel_of

        for source in ('facebook', 'fb', 'Instagram', 'ig', 'meta'):
            with self.subTest(source=source):
                self.assertEqual(_channel_of(SimpleNamespace(utm_source=source)), 'meta')
        self.assertEqual(_channel_of(SimpleNamespace(utm_source='google')), 'google')
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.analytics.tests.test_attribution`
Expected: FAIL.
- The window test fails with `Decimal('9300') != Decimal('300')`.
- The alias test fails with `'facebook' != 'meta'`.

- [ ] **Step 3: Fix `_channel_of` and `roas_by_channel`**

Replace `_channel_of` with:

```python
# Ad platforms whose traffic arrives under several utm_source spellings, keyed
# to the channel their spend is reported under (ANALYTICS_AD_SPEND).
_SOURCE_ALIASES = {'facebook': 'meta', 'fb': 'meta', 'instagram': 'meta', 'ig': 'meta'}


def _channel_of(session) -> str:
    source = (session.utm_source or '').strip().lower()
    return _SOURCE_ALIASES.get(source, source) or _DIRECT
```

In `roas_by_channel`, replace the two summing loops (from `spend: dict = defaultdict(Decimal)` through `revenue[channel] += Decimal(str(row['value_money'] or 0))`) with:

```python
    # Each snapshot is a trailing-window total already: read the newest day of
    # each, never the sum of every day (that counted each total up to 31 times).
    spend: dict = defaultdict(Decimal)
    spend_qs = AdSpendSnapshot.objects.filter(day__gte=since)
    newest_spend = spend_qs.order_by('-day').values_list('day', flat=True).first()
    for row in spend_qs.filter(day=newest_spend).values('channel', 'spend'):
        spend[row['channel']] += Decimal(str(row['spend'] or 0))

    revenue: dict = defaultdict(Decimal)
    prefix = f'{model}:'
    rev_qs = DailyMetric.objects.filter(
        metric='attribution', dimension__startswith=prefix, day__gte=since
    )
    newest_rev = rev_qs.order_by('-day').values_list('day', flat=True).first()
    for row in rev_qs.filter(day=newest_rev).values('dimension', 'value_money'):
        channel = row['dimension'][len(prefix) :]
        revenue[channel] += Decimal(str(row['value_money'] or 0))
```

Update the docstring to:
`"""Per-channel spend vs attributed revenue → ROAS, from the newest snapshot of each (both are trailing-window totals)."""`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$TEST plugins.installed.analytics plugins.installed.channels`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/analytics/services_attribution.py plugins/installed/analytics/tests/test_attribution.py
git commit -m "fix(analytics): ROAS reads one 30-day total, not 31 of them; facebook/ig traffic is Meta's

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Staff-entered URLs: the private-network check, and no redirects

**Files:**
- Modify:
  - `core/net.py` (add `outbound_request`)
  - `core/tasks.py` (`dispatch_webhook` uses it)
  - `plugins/installed/webhooks_ui/tasks.py` (uses it in place of `_refuse_unsafe_endpoint` + `requests.post`)
  - `plugins/installed/workflows/engine.py` (`_action_webhook_post`)
  - `plugins/installed/openai_shopping/tasks.py` (`push_feed`)
  - `plugins/installed/importers/adapters/shopify.py` and `woocommerce.py` (`get`)
- Test:
  - `core/tests/test_outbound_request.py`
  - `plugins/tests_outbound_sites.py`

**Interfaces:**
- Produces: `core.net.outbound_request(method: str, url: str, *, require_https: bool = True, field: str = 'url', **kwargs) -> requests.Response`.
  - It raises `UnsafeUrlError` for a bad scheme or a non-public host.
  - It lets an unresolvable host through to `requests`, so retry paths keep working.
  - It always sends `allow_redirects=False`.
  - It calls `requests.get` / `requests.post` by attribute at call time, so tests patching `requests.post` keep working.

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_outbound_request.py`:

```python
"""Server-initiated requests to staff-entered URLs: public hosts only, no redirects.

The two guarded webhook posts followed redirects, so a public URL answering 302
to 169.254.169.254 bypassed the check; the workflow action, the OpenAI feed push
and the importers had no check at all.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from core.net import UnsafeUrlError, outbound_request


class OutboundRequestTests(SimpleTestCase):
    def test_a_private_address_is_refused_before_any_request(self):
        with patch('requests.post') as post, self.assertRaises(UnsafeUrlError):
            outbound_request('POST', 'http://10.0.0.5/hook', require_https=False)
        post.assert_not_called()

    def test_https_is_required_unless_waived(self):
        with self.assertRaises(UnsafeUrlError):
            outbound_request('POST', 'http://example.com/x')

    def test_redirects_are_never_followed(self):
        with (
            patch('core.net.is_safe_remote_host', return_value=True),
            patch('requests.post') as post,
        ):
            outbound_request('POST', 'https://example.com/x', data=b'{}', timeout=5)
        self.assertIs(post.call_args.kwargs['allow_redirects'], False)
        self.assertEqual(post.call_args.args, ('https://example.com/x',))

    def test_get_uses_requests_get(self):
        with (
            patch('core.net.is_safe_remote_host', return_value=True),
            patch('requests.get') as get,
        ):
            outbound_request('GET', 'https://example.com/x', params={'a': 1})
        self.assertIs(get.call_args.kwargs['allow_redirects'], False)
```

Create `plugins/tests_outbound_sites.py`:

```python
"""Every staff-entered URL the server calls goes through core.net.outbound_request."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase


class OutboundSitesTests(TestCase):
    def test_a_workflow_cannot_post_to_the_private_network(self):
        from plugins.installed.workflows.engine import _action_webhook_post

        with patch('requests.post') as post:
            ok, msg = _action_webhook_post({'url': 'http://169.254.169.254/latest'}, {})
        self.assertFalse(ok)
        self.assertIn('not a public address', msg)
        post.assert_not_called()

    def test_the_feed_push_refuses_a_private_endpoint(self):
        from plugins.installed.openai_shopping.tasks import push_feed
        from plugins.registry import app_registry

        plugin = app_registry.get('openai_shopping')
        plugin.set_config('push_endpoint', 'https://127.0.0.1/ingest')
        plugin.set_config('push_token', 't')
        self.addCleanup(plugin.set_config, 'push_endpoint', '')
        self.addCleanup(plugin.set_config, 'push_token', '')
        with patch('requests.post') as post:
            result = push_feed()
        self.assertFalse(result['pushed'])
        post.assert_not_called()

    def test_the_woocommerce_importer_refuses_a_private_store(self):
        from core.net import UnsafeUrlError
        from plugins.installed.importers.adapters.woocommerce import _HTTPClient

        client = _HTTPClient(base_url='http://192.168.1.10', consumer_key='k', consumer_secret='s')
        with patch('requests.get') as get, self.assertRaises(UnsafeUrlError) as cm:
            client.get('products')
        get.assert_not_called()
        self.assertIn('not a public address', str(cm.exception))
```

(`FeedConfig.enabled` defaults to True, so the feed test sets only the endpoint and the token, as the existing `test_a_push_posts_the_feed_with_the_token` does.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$TEST core.tests.test_outbound_request plugins.tests_outbound_sites`
Expected:
- The core test ERRORs with `ImportError: cannot import name 'outbound_request'`.
- The site tests FAIL, because `requests.post` / `requests.get` were called.

- [ ] **Step 3: Add `outbound_request` (`core/net.py`, after `is_safe_outbound_url`)**

```python


def outbound_request(method: str, url: str, *, require_https: bool = True, field: str = 'url', **kwargs):
    """Send a server-initiated request to a URL someone entered (staff, an
    agent's setting, a webhook endpoint): public hosts only, never a redirect.

    A redirect is refused because the check covers only the first host — a
    public URL answering 302 to 169.254.169.254 would otherwise reach it. A host
    that does not resolve is let through so the caller's retry path handles it
    (an unresolvable host cannot be connected to).
    """
    import requests

    try:
        check_outbound_url(url, field=field, require_https=require_https)
    except UnresolvableHostError:
        pass
    kwargs['allow_redirects'] = False
    return getattr(requests, method.lower())(url, **kwargs)
```

- [ ] **Step 4: Use it at the call sites**

**`core/tasks.py`, `dispatch_webhook`.** Replace the `check_outbound_url` try-block and the `requests.post(...)` line with:

```python
    from core.net import UnsafeUrlError, outbound_request

    try:
        response = outbound_request(
            'POST', url, require_https=False, field='webhook url',
            data=body, headers=headers, timeout=10,
        )
    except UnsafeUrlError as e:
        logger.warning('Webhook refused by egress gate: %s -> %s (%s)', event_name, url, e)
        return
    except SoftTimeLimitExceeded:
```

Keep the existing `except SoftTimeLimitExceeded` and `except requests.exceptions.RequestException` branches attached to this `try`.

**`plugins/installed/webhooks_ui/tasks.py`.** Replace `if _refuse_unsafe_endpoint(d): return` and the `resp = requests.post(...)` line with:

```python
        from core.net import UnsafeUrlError, outbound_request

        try:
            resp = outbound_request(
                'POST', d.endpoint.url, require_https=False, field='endpoint.url',
                data=body, headers=headers, timeout=10,
            )
        except UnsafeUrlError as e:
            logger.warning('webhook refused by egress gate: %s -> %s', d.id, e)
            d.status = 'failed'
            d.response_body = f'refused: {e}'
            d.save(update_fields=['status', 'response_body'])
            return
```

Delete the now-unused `_refuse_unsafe_endpoint` function and the `import requests` above the call.

**`plugins/installed/workflows/engine.py`, `_action_webhook_post`.** Replace the `try: import requests …` block and the post with:

```python
    from core.net import UnsafeUrlError, outbound_request

    body = spec.get('body') or _serialize_payload(payload)
    headers = spec.get('headers') or {'Content-Type': 'application/json'}
    try:
        resp = outbound_request(
            'POST', url, require_https=False, field='webhook url',
            json=body, headers=headers, timeout=10,
        )
        return True, f'POST → {resp.status_code}'
    except UnsafeUrlError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, f'webhook error: {e}'
```

**`plugins/installed/openai_shopping/tasks.py`, `push_feed`.**
- Delete the `startswith('https://')` check, because `outbound_request` requires https.
- Replace `import requests` and `resp = requests.post(cfg.push_endpoint, …)` with `resp = outbound_request('POST', cfg.push_endpoint, field='push endpoint', data=…, headers=…, timeout=120)`, keeping its arguments.
- Add `from core.net import UnsafeUrlError, outbound_request` at the top of the function.
- Add, before the generic `except Exception as e:`:

```python
    except UnsafeUrlError as e:
        result['error'] = str(e)
```

**Importers.**
- In `shopify.py`, change the `get()` call to `resp = outbound_request('GET', url, field='shop', headers=self._headers, params=params, timeout=20)`.
- In `woocommerce.py`, change it to `resp = outbound_request('GET', url, require_https=False, field='store URL', auth=self._auth, params=params, timeout=20)`.
- Add `from core.net import outbound_request` to each module's imports. Remove `import requests` from each if nothing else in the file uses it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$TEST core.tests.test_outbound_request plugins.tests_outbound_sites core.tests_webhook_on_commit plugins.installed.webhooks_ui plugins.installed.workflows plugins.installed.openai_shopping plugins.installed.importers core.tests`
Expected: OK. If an existing test posts to a private or loopback host on purpose (for example `localhost` in a workflow test), switch it to `https://example.com/…` with `core.net.is_safe_remote_host` patched to True, and ledger it.

- [ ] **Step 6: Commit**

```bash
git add core/net.py core/tasks.py plugins/installed/webhooks_ui/tasks.py plugins/installed/workflows/engine.py plugins/installed/openai_shopping/tasks.py plugins/installed/importers/adapters/shopify.py plugins/installed/importers/adapters/woocommerce.py core/tests/test_outbound_request.py plugins/tests_outbound_sites.py
git commit -m "fix(security): staff-entered URLs get the private-network check and never follow redirects

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Docs, release, the whole suite and every gate

**Files:**
- Modify:
  - `CLAUDE.md`
  - `docs/plans/apps-consolidation-2026-10.md`
  - `docs/WEBHOOK_RECIPES.md`
  - `docs/MIGRATING.md`
  - `docs/API_STABILITY.md`
  - `docs/superpowers/specs/2026-10-15-wave0-live-fixes-design.md` (status line)
- Modified by `manage.py release`: `docs/RELEASE_NOTES.md` and `morph/settings.py` (`MORPHEUS_VERSION`)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Update `CLAUDE.md`**

At the end of the paragraph that begins `**Landmine — a consent banner that nothing reads is a banner, not consent;`, append:

```
Since v0.113.0 the server-side sends obey it too: the conversion APIs, GA4 Measurement Protocol, the Google Ads purchase tag and `meta.sync_audience` ask `core/consent.py:allowed()`, which reads the shopper's choice stamped on the order at checkout (`metadata['consent']` — a payment webhook has no visitor to ask), else the request, else the store, and refuses without evidence on a store that manages consent. The consent app answers through `CONSENT_DECISION` / `CONSENT_MARKETING_CUSTOMERS`, so core imports nothing; the tracking app's second banner is gone. Guarded by `consent/tests/test_server_side_consent.py`, `plugins/tests_capi_consent.py` and `tracking/tests/test_consent_gate.py`.
```

In the guardrails landmine, after the sentence ending `…never a raw provider.` in item (4), append:

```
(5) **The provider class is guarded too (v0.113.0):** `core.agents.llm.LLMProvider.__init_subclass__` wraps every `respond` (`guardrails.guard_model_call`) — six callers reached a model there directly. A refusal raises `guardrails.AIPaused`; a call outside the runtime's own `run_scope()` is recorded in `ModelUsageDay`, which `daily_spend_usd` adds, so a tool that calls a model inside a run is counted while the run's own calls (stored on the `AgentRun`) are not counted twice. Embeddings and text-to-speech obey the kill switch. Guarded by `core/agents/tests/test_provider_guard.py`.
```

After the paragraph that begins `**Landmine — a hook with subscribers but no producer`, add:

```

**Convention — one webhook trigger (v0.113.0).** Core's `_dispatch_remote` decides when (after commit) and to whom (an endpoint's events, or `'*'`); the delivery goes through the `WEBHOOK_DELIVER` filter, which webhooks_ui answers (log, retries, dead-letter, replay), and core posts itself when nothing answers. webhooks_ui used to subscribe its own fan-out as well, so an endpoint got two POSTs in two shapes, one of them before commit. Never add a second subscriber that posts. Every staff-entered URL the server calls goes through `core.net.outbound_request` (public hosts, no redirects). Guarded by `webhooks_ui/tests/test_one_trigger.py` and `core/tests/test_outbound_request.py`.
```

- [ ] **Step 2: Update the other docs**

- **`docs/plans/apps-consolidation-2026-10.md`.** Replace the Status paragraph's last sentence, "Item 3 (consent) and items 8 to 10 are open.", with: "Items 3 and 8–10 shipped in v0.113.0 (spec `docs/superpowers/specs/2026-10-15-wave0-live-fixes-design.md`). Not done there: AI provider base URLs need an allowlist, and the `markets` middleware goes with that app in wave 2."
- **`docs/WEBHOOK_RECIPES.md`.** Under `## Signature verification`, after the code block, add:

  ```
  **Body.** The request body is the event's payload as canonical JSON (sorted keys, no spaces); the event name is in the `X-Morpheus-Event` header. A model appears as its identifying fields — `{"id", "model", "order_number"/"sku"/"email"/"name"/"slug"/"status" when it has them}`, never a record dump. Each delivery carries `X-Morpheus-Delivery` (its id in the delivery log) and `X-Morpheus-Attempt`. Since v0.113.0 every endpoint receives one POST per event, after the transaction commits, and redirects are not followed.
  ```

- **`docs/MIGRATING.md`.** Insert after the intro's `---` line:

  ```
  ## v0.113.0 — one webhook per event, in one shape

  A merchant webhook endpoint used to receive each event twice: once from core, as the bare payload, and once from the Webhooks app, as `{"event": …, "data": …}`, sometimes before the order was saved. It now receives one POST, after commit, whose body is the bare payload (canonical JSON) with the event name in `X-Morpheus-Event`. A receiver that read `body["event"]` or `body["data"]` reads the header and the body itself. Webhook targets must be public hosts and redirects are not followed — point an endpoint at its final URL.
  ```

- **`docs/API_STABILITY.md`.** Add a row at the top of the "Breaking changes shipped" table:

  ```
  | **v0.113.0** | Merchant webhooks | One POST per event after commit (was two, one possibly before commit); the body is the bare payload (the `{"event","data"}` envelope is gone); redirects are not followed and private hosts are refused. | [`MIGRATING.md`](MIGRATING.md#v01130--one-webhook-per-event-in-one-shape) |
  ```

- **The spec.** Change its `**Status:**` line to `**Status:** shipped in v0.113.0.`

- [ ] **Step 3: Cut the release**

Run:
```bash
.venv/bin/python manage.py release --minor "Nothing leaves the store without consent; AI stops when you say stop" \
  -m "Conversion APIs (Meta, TikTok, Pinterest, Snapchat, Reddit), GA4 server events, the Google Ads tag and Meta audience sync send only what the shopper agreed to; the order records the choice at checkout. Stores that don't ask for consent are unchanged." \
  -m "Every AI call obeys the kill switch and the daily spend cap, including page help, the brain, the briefing, autopilot, self-improvement, description fill, embeddings and narration; their spend now counts." \
  -m "Visitors and crawlers no longer cost a session write or lose the edge cache; expired sessions are cleared daily." \
  -m "Merchant webhooks: one POST per event after commit, in one shape; staff-entered URLs must be public and redirects are not followed." \
  -m "Attribution: ROAS reads one 30-day total (was ~31x), and Facebook/Instagram traffic counts as Meta."
.venv/bin/python manage.py release --check
```
Expected: the version is v0.113.0, a dated notes entry exists, and `release --check` passes.

- [ ] **Step 4: Run every gate**

Run:
```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . \
 && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py check \
 && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run \
 && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py \
 && .venv/bin/python scripts/check_plugin_standard.py \
 && for d in plugins/installed/*/migrations; do [ -f "$d/__init__.py" ] || echo "MISSING $d"; done; echo gates-done
```
Expected:
- ruff reports "All checks passed!" and every file is formatted.
- `check` reports no issues.
- `makemigrations` reports "No changes detected".
- The boundary and standard scripts pass at 0, 113 and 38.
- No `MISSING` lines, ending with `gates-done`.

If `check_plugin_standard.py` fails because an app gained its first tests (none of this plan's apps lacked tests, but check), run `--save` and include the baseline in the commit.

- [ ] **Step 5: Run the full suite (in the background)**

Run:
`DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > .superpowers/sdd/full-suite.log 2>&1; tail -30 .superpowers/sdd/full-suite.log`

Expected: `OK`, with about 4,832 + the new tests. Every failure is fixed, or recorded by name in the ledger with its cause; none is passed over.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md docs/plans/apps-consolidation-2026-10.md docs/WEBHOOK_RECIPES.md docs/MIGRATING.md docs/API_STABILITY.md docs/superpowers/specs/2026-10-15-wave0-live-fixes-design.md docs/RELEASE_NOTES.md morph/settings.py
git commit -m "chore(release): v0.113.0 — Nothing leaves the store without consent; AI stops when you say stop

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Deploy, then verify on the live stores

**Files:** none. This task is operations: a push to main deploys every store through Coolify.

- [ ] **Step 1: Push and wait for every store**

Run: `git push origin main && SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh v0.113.0`
Expected: every store's `/readyz` reports v0.113.0.

If a store stalls, follow the Coolify stuck-queue recovery in `docs/OPERATIONS_RUNBOOK.md` (force a deploy by API).

- [ ] **Step 2: No session cookie for a visitor, on every store**

For each storefront host that `scripts/deploy_smoke.sh` checks:
- **The home page as a browser:**
  `curl -s -o /dev/null -D - -A 'Mozilla/5.0 (Macintosh) Safari/605.1.15' "https://$HOST/?cb=$RANDOM" | grep -i '^set-cookie: sessionid' || echo "$HOST /: no sessionid"`
- **One product page as Googlebot** (take its path from the store's `sitemap.xml`; on Montenegro use an experience page under `/bookings/`):
  `curl -s -o /dev/null -D - -A 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)' "https://$HOST$PRODUCT?cb=$RANDOM" | grep -i '^set-cookie: sessionid' || echo "$HOST $PRODUCT: no sessionid"`

Expected: every line reads `no sessionid`. A browser on a product page still gets a session, because that is the recently-viewed list.

- [ ] **Step 3: Clear the backlog of expired sessions, once, on each store**

Over `~/.ssh/tetra-ssh.sh`, for each store's web container (pin the container uuids from Coolify):

`docker exec <web> python manage.py shell -c "from django.contrib.sessions.models import Session as S; print(S.objects.count())"`, then
`docker exec <web> python manage.py clearsessions`, then the count again.

Record before and after for each store in the final report.

- [ ] **Step 4: Spot-check the live behaviour**
  - On the store with Google Ads conversion ids configured (if any), render an order confirmation without a consent cookie and confirm the `gtag("event","conversion"` script is absent. If no store has ids configured, say so; the tag cannot render there and the unit test is the proof.
  - On one store, open Settings → Tracking and confirm the banner settings are gone and the page loads (200).
  - Confirm `/dashboard/apps/` shows `agent_mcp` with no disable control.

- [ ] **Step 5: Report**

Report what shipped, with the live numbers: the cookie check per store, and sessions cleared per store. Also report anything not verified, and the deferred items from the spec's "Left out" lines.
