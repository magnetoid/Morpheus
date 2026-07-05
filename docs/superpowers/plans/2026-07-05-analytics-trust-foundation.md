# Analytics Trust Foundation (Slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Morpheus analytics numbers correct and trustworthy (funnel 500, dead checkout metric, ad-blocker-inflated CVR, forgeable beacon, consent-inflating sessions), surface analytics on the dashboard home, and land a first anomaly alert — zero migrations.

**Architecture:** All logic stays in `plugins/installed/analytics/` per the plugin contract; storefront views only gain fail-soft `core.hooks` fires (no analytics imports). Server-side hooks become the source of funnel truth; the client beacon is demoted to enrichment. Derived KPIs roll into the existing `DailyMetric` table (ratios as basis points in `value_int` — deliberate deviation from the spec's "percents in value_money": `value_int` is a plain BigInteger, `value_money` is a currency-tagged MoneyField that would mistype a ratio).

**Tech Stack:** Django 5 / Celery beat / Postgres (prod) + sqlite (tests) / `core.hooks` bus / `django.core.cache` for rate limiting / Python `statistics` for anomaly math (no new deps).

**Spec:** `docs/superpowers/specs/2026-07-05-analytics-trust-foundation-design.md`

## Global Constraints

- Zero migrations — no model changes anywhere in this slice.
- Test command (always): `DATABASE_URL='sqlite:///:memory:' python manage.py test <target>` (bare `manage.py test` hangs on the Docker `db` host).
- Cross-plugin coupling ONLY via `core.hooks` — storefront must not import analytics.
- Every hook fire in a storefront view is wrapped `try/except Exception: pass` (never break a render).
- Ruff must pass per file before commit (PostToolUse hook enforces; CI pins ruff 0.15.8).
- Commit after every task; do NOT push (push = prod deploy; user says "ship").
- Canonical event names come from `core/hooks.py:MorpheusEvents` (`checkout.started`, `product.viewed`, `search.performed`); the dynamic mirror `morpheus.events` exposes them as `events.BEGIN_CHECKOUT` etc.

## Known code facts (verified — trust these, don't re-derive)

- `services.py:funnel_for` returns `[{'step': <name>, 'sessions': <int>}, …]`; `services_cohorts.py:step_dropoffs` L265-266 wrongly reads `prev['name']`/`cur['name']`.
- `plugin.py:ready()` hook fan-out list (L35-42) has NO `events.BEGIN_CHECKOUT` — checkout events never land at all.
- `tasks.py:_kind_for` (L37) maps BOTH `order.placed` and `payment.captured` → `'purchase'`; `roll_daily` aggregates revenue over `kind='purchase'` → double-count exposure.
- `services.py:roll_daily` L296 counts `name='checkout.start'` (wrong name); `views.py:funnel_view` L260 default steps `['pageview', 'product.viewed', 'cart.add', 'order.placed']`.
- `views.py:_ALLOWED_KINDS` (L22) includes client-forgeable `'purchase', 'checkout', 'signup', 'login'`.
- `services.py:get_or_create_session` reads `request.COOKIES.get('cookie_consent') == 'true'` but creates an `AnalyticsSession` row even when not consented (only the cookie-set is gated) → a new row per request for non-consented visitors.
- `record_event(request=…, session=None)` resolves the session itself; `session=None` is fully supported (events row with `session=NULL`).
- `plugin.py:_on_event(event_name)` builds a `**kwargs` handler; it currently extracts `order`/`product`/`customer` kwargs only — no `request`, no `query`.
- Checkout already fires `MorpheusEvents.BEGIN_CHECKOUT` (kwargs `cart=`, `customer=`) in `storefront/views/checkout.py:~203` and `checkout_one_page.py:~55`, gated by `request.session['checkout_started']`.
- The dot_books theme beacon sends ONLY web-vitals (`base.html:832`); no client code sends `product_view`/`search`/`cart` kinds → server emitters introduce no double counting.
- `DailyMetric` fields: `day` (date), `metric` (str), `dimension` (str), `value_int` (BigInteger), `value_money` (MoneyField, nullable). Unique on `(day, metric, dimension)`.
- KPI dict shape (see `catalog/plugin.py:on_dashboard_kpis`): `{'label', 'value', 'delta', 'trend', 'icon', 'series', 'hint'}` appended to `value` list; handler signature `(self, value, date_range=None, **kwargs)`.
- Activity item shape (see `admin_dashboard/plugin.py:on_activity_feed`): `{'kind', 'icon', 'label', 'hint', 'url', 'when'}`; handler `(self, value, limit=20, **kwargs)`.
- Notifications: `plugins.installed.notifications_center.services.notify_all_staff(kind=…, title=…, body=…, action_url=…, icon=…)` — import in try/except ImportError (pattern: `inventory/tasks.py:14`).
- Dashboard URLs: funnel = `/dashboard/analytics/v2/funnel/`, cohorts = `/dashboard/analytics/v2/cohorts/` (namespace `analytics_dash`).
- Existing test file: `plugins/installed/analytics/tests/test_analytics.py` (`SessionTests`, `RecordEventTests`, `RollupTests`, `FunnelTests`, …) — TestCase style, no pytest.

---

### Task 1: Fix the funnel 500

**Files:**
- Modify: `plugins/installed/analytics/services_cohorts.py:265-266`
- Test: `plugins/installed/analytics/tests/test_funnel_dropoffs.py` (create)

**Interfaces:**
- Consumes: `funnel_for(steps=…, days=…)` → `[{'step', 'sessions'}]`
- Produces: `step_dropoffs(steps=…, days=…)` → `[{'from_step', 'to_step', 'prev_count', 'cur_count', 'lost', 'dropoff_pct'}]` (unchanged contract, now non-crashing)

- [ ] **Step 1: Write the failing tests**

```python
# plugins/installed/analytics/tests/test_funnel_dropoffs.py
"""Funnel drop-off — regression for the KeyError('name') 500 (step_dropoffs
read prev['name'] but funnel_for returns {'step', 'sessions'})."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.analytics.models import AnalyticsSession
from plugins.installed.analytics.services import record_event
from plugins.installed.analytics.services_cohorts import step_dropoffs


def _session(n: str) -> AnalyticsSession:
    return AnalyticsSession.objects.create(cookie_id=f'ck-{n}')


def _seed_two_step_funnel():
    """3 sessions hit step one, 1 continues to step two."""
    for i in range(3):
        s = _session(str(i))
        record_event(name='pageview', kind='pageview', session=s)
    survivor = AnalyticsSession.objects.first()
    record_event(name='product.viewed', kind='product_view', session=survivor)


class StepDropoffsTests(TestCase):
    def test_two_steps_no_keyerror_and_correct_keys(self):
        _seed_two_step_funnel()
        rows = step_dropoffs(steps=['pageview', 'product.viewed'], days=30)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['from_step'], 'pageview')
        self.assertEqual(rows[0]['to_step'], 'product.viewed')
        self.assertEqual(rows[0]['prev_count'], 3)
        self.assertEqual(rows[0]['cur_count'], 1)


class FunnelViewTests(TestCase):
    def test_funnel_page_renders_200_with_data(self):
        _seed_two_step_funnel()
        staff = get_user_model().objects.create_user(
            email='staff@test.local', password='x', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get(
            '/dashboard/analytics/v2/funnel/',
            {'steps': 'pageview,product.viewed'},
        )
        self.assertEqual(resp.status_code, 200)
```

Note: if `create_user` requires `username` in this project, check `SessionTests` in
`test_analytics.py` and copy its user-creation call exactly (USERNAME_FIELD is `email`).

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_funnel_dropoffs -v 2`
Expected: `StepDropoffsTests` FAILS with `KeyError: 'name'` (and `FunnelViewTests` 500s for the same reason).

- [ ] **Step 3: Fix the keys**

In `plugins/installed/analytics/services_cohorts.py` (L265-266), change:

```python
                'from_step': prev['name'],
                'to_step': cur['name'],
```

to:

```python
                'from_step': prev['step'],
                'to_step': cur['step'],
```

- [ ] **Step 4: Run to verify it passes**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_funnel_dropoffs -v 2`
Expected: PASS (both classes).

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/analytics/services_cohorts.py plugins/installed/analytics/tests/test_funnel_dropoffs.py
git commit -m "fix(analytics): funnel drop-off 500 — step_dropoffs read prev['name'] but funnel_for emits 'step'"
```

---

### Task 2: Checkout events actually land — subscribe + canonical name + single money event

**Files:**
- Modify: `plugins/installed/analytics/plugin.py` (ready() fan-out list, ~L35-42)
- Modify: `plugins/installed/analytics/tasks.py:_kind_for` (~L37)
- Modify: `plugins/installed/analytics/services.py:roll_daily` (~L296)
- Modify: `plugins/installed/analytics/views.py` (~L260 default steps)
- Test: `plugins/installed/analytics/tests/test_checkout_pipeline.py` (create)

**Interfaces:**
- Consumes: `MorpheusEvents.BEGIN_CHECKOUT == 'checkout.started'`; checkout views already fire it.
- Produces: `_kind_for('checkout.started') == 'checkout'`; `_kind_for('payment.captured')` falls through to `'custom'` (only `order.placed` is `'purchase'`); `roll_daily` upserts `checkouts_started` from `name='checkout.started'`.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/installed/analytics/tests/test_checkout_pipeline.py
"""checkout.started must flow hook → event → rollup, and order.placed must be
the ONLY purchase-kind event (payment.captured double-counted revenue)."""

from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric
from plugins.installed.analytics.services import roll_daily
from plugins.installed.analytics.tasks import _kind_for


class KindForTests(TestCase):
    def test_checkout_started_maps_to_checkout(self):
        self.assertEqual(_kind_for('checkout.started'), 'checkout')

    def test_only_order_placed_is_purchase(self):
        self.assertEqual(_kind_for('order.placed'), 'purchase')
        self.assertNotEqual(_kind_for('payment.captured'), 'purchase')


class CheckoutHookTests(TestCase):
    def test_begin_checkout_hook_records_event(self):
        hook_registry.fire(MorpheusEvents.BEGIN_CHECKOUT, cart=None, customer=None)
        self.assertTrue(
            AnalyticsEvent.objects.filter(name='checkout.started').exists(),
            'analytics must subscribe to BEGIN_CHECKOUT',
        )


class CheckoutRollupTests(TestCase):
    def test_roll_daily_counts_checkout_started(self):
        AnalyticsEvent.objects.create(name='checkout.started', kind='checkout')
        AnalyticsEvent.objects.filter(name='checkout.started').update(
            created_at=timezone.now() - timezone.timedelta(days=1)
        )
        roll_daily()
        row = DailyMetric.objects.get(metric='checkouts_started', dimension='')
        self.assertEqual(row.value_int, 1)
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_checkout_pipeline -v 2`
Expected: `test_checkout_started_maps_to_checkout` fails (`_kind_for` returns `'custom'`), `test_begin_checkout_hook_records_event` fails (no subscription), `test_roll_daily_counts_checkout_started` fails (counts `'checkout.start'`).

- [ ] **Step 3: Implement**

`plugins/installed/analytics/plugin.py` — add `events.BEGIN_CHECKOUT` to the fan-out list:

```python
        for event in [
            events.ORDER_PLACED,
            events.PAYMENT_CAPTURED,
            events.BEGIN_CHECKOUT,
            events.PRODUCT_VIEWED,
            events.SEARCH_PERFORMED,
            events.CUSTOMER_REGISTERED,
            events.CART_ABANDONED,
        ]:
            self.register_hook(event, self._on_event(event), priority=99)
```

`plugins/installed/analytics/tasks.py:_kind_for` — first branch becomes:

```python
def _kind_for(name: str) -> str:  # noqa: PLR0911
    # Only order.placed is the canonical money event — payment.captured used
    # to map to 'purchase' too, double-counting revenue in roll_daily.
    if name == 'order.placed':
        return 'purchase'
    if name == 'checkout.started':
        return 'checkout'
    if name == 'product.viewed':
        return 'product_view'
```

(rest of the function unchanged; `payment.captured` now falls through to `'custom'`).

`plugins/installed/analytics/services.py` L296:

```python
    upsert('checkouts_started', value_int=qs.filter(name='checkout.started').count())
```

`plugins/installed/analytics/views.py` L260 default steps:

```python
        steps = ['pageview', 'product.viewed', 'cart.add', 'checkout.started', 'order.placed']
```

- [ ] **Step 4: Run to verify it passes + no regressions**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics -v 1`
Expected: all PASS. If `RollupTests.test_roll_daily_writes_metrics` asserts on revenue with a `payment.captured` fixture, update that fixture to `order.placed` (the double-count was the bug).

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/analytics/
git commit -m "fix(analytics): checkout events land — subscribe BEGIN_CHECKOUT, canonical checkout.started, single purchase event"
```

---

### Task 3: Server-side funnel emitters (PDP + search) with session linkage

**Files:**
- Modify: `plugins/installed/analytics/plugin.py:_on_event` (~L71-104)
- Modify: `plugins/installed/storefront/views/catalog.py` (`product_detail` ~L331 region, `search` ~L857)
- Modify: `plugins/installed/storefront/views/checkout.py` (~L203-213) and `checkout_one_page.py` (~L55-64) — add `request=request` to the existing fires
- Test: `plugins/installed/analytics/tests/test_server_emitters.py` (create)

**Interfaces:**
- Consumes: `record_event(request=…)` resolves the session; `get_or_create_session(request)`.
- Produces: hook fires now carry `request=` (additive kwarg — handlers are `**kwargs`, safe); `_on_event` passes `request`, `search_query`, and `url` through to `record_event`, so server events carry sessions and appear in session-based funnels.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/installed/analytics/tests/test_server_emitters.py
"""Server-side PRODUCT_VIEWED / SEARCH_PERFORMED events must carry the
visitor's session (funnels join on session_id) and the search query."""

from __future__ import annotations

from django.test import RequestFactory, TestCase

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent


class _FakeProduct:
    slug = 'test-book'


class ServerEmitterTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _request(self):
        req = self.rf.get('/products/test-book/')
        req.user = type('Anon', (), {'is_authenticated': False})()
        req.COOKIES['cookie_consent'] = 'true'
        req.COOKIES['morph_aid'] = 'ck-emitter-test-0000000000000000'
        return req

    def test_product_viewed_hook_records_event_with_session(self):
        hook_registry.fire(
            MorpheusEvents.PRODUCT_VIEWED,
            product=_FakeProduct(),
            customer=None,
            request=self._request(),
        )
        evt = AnalyticsEvent.objects.get(name='product.viewed')
        self.assertEqual(evt.product_slug, 'test-book')
        self.assertIsNotNone(evt.session_id, 'server event must carry a session')

    def test_search_performed_hook_records_query(self):
        hook_registry.fire(
            MorpheusEvents.SEARCH_PERFORMED,
            query='dune',
            results_count=3,
            request=self._request(),
        )
        evt = AnalyticsEvent.objects.get(name='search.performed')
        self.assertEqual(evt.search_query, 'dune')
        self.assertIsNotNone(evt.session_id)
```

Check the analytics cookie name first: `grep -n "COOKIE_NAME" plugins/installed/analytics/services.py` — use its literal value in the test (assumed `morph_aid`; fix the test if different).

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_server_emitters -v 2`
Expected: FAIL — `session_id` is None (handler ignores `request`), `search_query` empty.

- [ ] **Step 3: Extend `_on_event`**

Replace the handler body in `plugins/installed/analytics/plugin.py:_on_event`:

```python
        def _handler(**kwargs):
            try:
                from plugins.installed.analytics.services import record_event
                from plugins.installed.analytics.tasks import _kind_for

                revenue = None
                product_slug = ''
                customer = None
                if 'order' in kwargs:
                    order = kwargs.get('order')
                    revenue = getattr(order, 'total', None)
                    customer = getattr(order, 'customer', None)
                if 'product' in kwargs:
                    product = kwargs.get('product')
                    product_slug = getattr(product, 'slug', '') or ''
                if 'customer' in kwargs:
                    customer = kwargs.get('customer')

                # Server-side storefront fires pass request= so the event
                # joins the visitor's session (funnels group by session_id).
                request = kwargs.get('request')
                record_event(
                    name=event_name,
                    kind=_kind_for(event_name),
                    request=request,
                    customer=customer,
                    revenue=revenue,
                    product_slug=product_slug,
                    search_query=str(kwargs.get('query') or '')[:200],
                    url=(getattr(request, 'path', '') or '')[:500],
                    payload={'src': 'hook'},
                )
            except Exception:  # noqa: BLE001, S110
                pass
```

- [ ] **Step 4: Fire the hooks from the storefront views**

`plugins/installed/storefront/views/catalog.py:product_detail` — after `product_row`
is resolved (it already exists in the function; find `product_row = (` and insert
after that block, before the render):

```python
    # Server-side analytics: the funnel's product.viewed truth. Client
    # beacons are ad-blockable; this is not. Fail-soft — never break a PDP.
    try:
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

        if product_row is not None:
            hook_registry.fire(
                MorpheusEvents.PRODUCT_VIEWED,
                product=product_row,
                customer=request.user if request.user.is_authenticated else None,
                request=request,
            )
    except Exception:  # noqa: BLE001, S110
        pass
```

`plugins/installed/storefront/views/catalog.py:search` — the plain-keyword branch
redirects to `/products/?q=…`; fire on the semantic branch AND in the PLP-redirect
target is wrong altitude — instead fire once here before the redirect/render, only
when `q` is non-empty:

```python
def search(request):
    q = request.GET.get('q', '').strip()
    use_semantic = request.GET.get('mode') == 'semantic'

    if q:
        # Server-side analytics: search.performed truth (ad-blocker-proof).
        try:
            from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

            hook_registry.fire(
                MorpheusEvents.SEARCH_PERFORMED,
                query=q,
                results_count=None,
                request=request,
            )
        except Exception:  # noqa: BLE001, S110
            pass
```

(keep the rest of the function unchanged).

`checkout.py` (~L208) and `checkout_one_page.py` (~L60): add `request=request,` to the
existing `hook_registry.fire(MorpheusEvents.BEGIN_CHECKOUT, cart=cart, customer=…)` calls
so checkout events join the session too.

- [ ] **Step 5: Run to verify**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics plugins.installed.storefront -v 1`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/analytics/ plugins/installed/storefront/views/
git commit -m "feat(analytics): server-side funnel truth — PDP/search/checkout hooks carry request → session-linked events"
```

---

### Task 4: Beacon lockdown — no client-forgeable kinds + per-IP rate limit

**Files:**
- Modify: `plugins/installed/analytics/views.py` (`_ALLOWED_KINDS` L22, `track_beacon` ~L64)
- Test: `plugins/installed/analytics/tests/test_beacon_lockdown.py` (create)

**Interfaces:**
- Produces: `_ALLOWED_KINDS` without `purchase`/`checkout`/`signup`/`login` (submitting those → stored as `'custom'`); `track_beacon` returns 429 beyond 120 events/min/IP.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/installed/analytics/tests/test_beacon_lockdown.py
"""The beacon must not accept client-forgeable money/auth kinds, and must
rate-limit per IP (an open unauthenticated POST endpoint)."""

from __future__ import annotations

import json

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.analytics.models import AnalyticsEvent

_URL = '/api/analytics/track/'  # verify: grep urls_api.py for the beacon path


class BeaconKindTests(TestCase):
    def _post(self, kind):
        return self.client.post(
            _URL,
            data=json.dumps({'name': f'evt-{kind}', 'kind': kind}),
            content_type='application/json',
        )

    def test_money_and_auth_kinds_downgrade_to_custom(self):
        for kind in ('purchase', 'checkout', 'signup', 'login'):
            self._post(kind)
            evt = AnalyticsEvent.objects.get(name=f'evt-{kind}')
            self.assertEqual(evt.kind, 'custom', f'{kind} must not be client-settable')


class BeaconRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_121st_event_in_a_minute_is_429(self):
        for i in range(120):
            resp = self.client.post(
                _URL,
                data=json.dumps({'name': f'e{i}', 'kind': 'click'}),
                content_type='application/json',
            )
            self.assertNotEqual(resp.status_code, 429)
        resp = self.client.post(
            _URL,
            data=json.dumps({'name': 'e-last', 'kind': 'click'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 429)
```

First verify the beacon URL: `grep -n "track" plugins/installed/analytics/urls_api.py`
and the URL prefix in `plugin.py:register_urls` (`prefix='api/'`) — adjust `_URL`.
Also check whether the endpoint is csrf-exempt (it must be, for sendBeacon) — if the
test 403s, use `self.client.post(..., HTTP_X_CSRFTOKEN=...)` or the csrf_exempt reality.

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_beacon_lockdown -v 2`
Expected: kind test FAILS (`purchase` stored as `purchase`); rate-limit test FAILS (no 429).

- [ ] **Step 3: Implement**

`views.py` `_ALLOWED_KINDS` — remove the four kinds:

```python
_ALLOWED_KINDS = {
    'pageview',
    'product_view',
    'search',
    'cart',
    'custom',
    'click',
    'form_submit',
    # NOTE: 'purchase'/'checkout'/'signup'/'login' are deliberately absent —
    # money/auth truth comes from server-side hooks only (order.placed,
    # checkout.started, customer.registered). A forged client event would
    # inflate revenue/conversion.
}
```

(keep any other members the set currently has — only delete those four.)

`views.py:track_beacon` — at the top, after the body-size check:

```python
    # Per-IP rate limit: open unauthenticated endpoint. Cache counter,
    # 120 events/min; race-tolerant (worst case a few extra slip through).
    ip = request.META.get('REMOTE_ADDR', '') or 'unknown'
    rl_key = f'analytics:beacon-rl:{ip}'
    from django.core.cache import cache  # noqa: PLC0415

    cache.add(rl_key, 0, timeout=60)
    try:
        count = cache.incr(rl_key)
    except ValueError:  # key expired between add and incr
        count = 1
    if count > 120:
        return HttpResponse(status=429)
```

- [ ] **Step 4: Run to verify + full plugin suite**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics -v 1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/analytics/
git commit -m "feat(analytics): beacon lockdown — server-only money/auth kinds + 120/min/IP rate limit"
```

---

### Task 5: Consent-gate ingestion (no session rows for non-consented visitors)

**Files:**
- Modify: `plugins/installed/analytics/services.py:get_or_create_session` (~L109)
- Modify (if assertions break): `plugins/installed/analytics/tests/test_analytics.py` fixtures
- Test: `plugins/installed/analytics/tests/test_consent_gating.py` (create)

**Interfaces:**
- Produces: `get_or_create_session(request, response=…)` returns `None` when `request.COOKIES.get('cookie_consent') != 'true'`; callers (`middleware`, `track_beacon`, `record_event`) already handle `session=None`.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/installed/analytics/tests/test_consent_gating.py
"""Non-consented visitors must not mint AnalyticsSession rows (one per
request today — inflates `sessions`) and must not receive the cookie."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession


class ConsentGatingTests(TestCase):
    def test_no_session_without_consent(self):
        self.client.get('/')
        self.client.get('/')
        self.assertEqual(AnalyticsSession.objects.count(), 0)

    def test_pageview_still_recorded_sessionless(self):
        self.client.get('/')
        evt = AnalyticsEvent.objects.filter(kind='pageview').first()
        self.assertIsNotNone(evt)
        self.assertIsNone(evt.session_id)

    def test_consented_visitor_gets_one_session(self):
        self.client.cookies['cookie_consent'] = 'true'
        self.client.get('/')
        self.client.get('/')
        self.assertEqual(AnalyticsSession.objects.count(), 1)
```

(If `/` isn't tracked in the test env — e.g. storefront disabled — use any
storefront GET path the middleware covers; check `_EXCLUDED_PREFIXES`.)

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_consent_gating -v 2`
Expected: `test_no_session_without_consent` FAILS (2 rows created).

- [ ] **Step 3: Implement**

In `services.py:get_or_create_session`, right after `is_consented` is computed:

```python
    cookie_id = (request.COOKIES.get(COOKIE_NAME) or '').strip()
    is_consented = request.COOKIES.get('cookie_consent') == 'true'

    # GDPR/ePrivacy: no consent → no visitor-level persistence. Events still
    # record session-less (aggregate counts stay honest) and server-side
    # commerce events carry customer when known. Previously a fresh
    # AnalyticsSession row was minted per request here, inflating `sessions`.
    if not is_consented:
        return None
```

- [ ] **Step 4: Run the FULL analytics suite and repair fixtures**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics -v 1`
Expected: `test_consent_gating` passes. `SessionTests` (and any test asserting
session creation through requests) will now fail — fix each by setting the consent
cookie in the test client before the request:

```python
self.client.cookies['cookie_consent'] = 'true'
```

(or `req.COOKIES['cookie_consent'] = 'true'` for RequestFactory tests). Do NOT
weaken the assertions — only add consent to fixtures that represent consented
visitors. Re-run until green.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/analytics/
git commit -m "feat(analytics): consent-gated ingestion — no session rows or cookies without consent"
```

---

### Task 6: Derived KPI rollups + Cohorts in nav

**Files:**
- Modify: `plugins/installed/analytics/services.py:roll_daily` (after the existing upserts, before the loops)
- Modify: `plugins/installed/analytics/plugin.py:contribute_dashboard_pages`
- Test: `plugins/installed/analytics/tests/test_derived_rollups.py` (create)

**Interfaces:**
- Produces: `DailyMetric` rows — `conversion_rate` (basis points in `value_int`: 240 = 2.40%), `aov` (`value_money`), `cart_abandonment` (basis points in `value_int`). Task 7 reads `conversion_rate`.
- Deviation from spec (documented): ratios in `value_int` as basis points, not "percents in value_money" — `value_money` is currency-tagged (MoneyField) and would mistype a ratio; `aov` (a real money amount) uses `value_money`.

- [ ] **Step 1: Write the failing test**

```python
# plugins/installed/analytics/tests/test_derived_rollups.py
"""Derived daily KPIs — conversion_rate/aov/cart_abandonment must roll into
DailyMetric so history survives the 90-day raw-event trim."""

from __future__ import annotations

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.analytics.models import (
    AnalyticsEvent,
    AnalyticsSession,
    DailyMetric,
)
from plugins.installed.analytics.services import roll_daily


class DerivedRollupTests(TestCase):
    def _seed_yesterday(self):
        yesterday = timezone.now() - timezone.timedelta(days=1)
        sessions = [
            AnalyticsSession.objects.create(cookie_id=f'ck-{i}') for i in range(4)
        ]
        for s in sessions:
            AnalyticsEvent.objects.create(name='pageview', kind='pageview', session=s)
        AnalyticsEvent.objects.create(
            name='cart.add', kind='cart', session=sessions[0]
        )
        AnalyticsEvent.objects.create(
            name='cart.add', kind='cart', session=sessions[1]
        )
        AnalyticsEvent.objects.create(
            name='checkout.started', kind='checkout', session=sessions[0]
        )
        AnalyticsEvent.objects.create(
            name='order.placed',
            kind='purchase',
            session=sessions[0],
            revenue=Money(50, 'USD'),
        )
        AnalyticsEvent.objects.update(created_at=yesterday)

    def test_derived_metrics_written(self):
        self._seed_yesterday()
        roll_daily()
        # 1 purchase / 4 sessions = 25.00% = 2500 bp
        self.assertEqual(
            DailyMetric.objects.get(metric='conversion_rate').value_int, 2500
        )
        # revenue 50 / 1 order = 50.00
        self.assertEqual(
            DailyMetric.objects.get(metric='aov').value_money, Money(50, 'USD')
        )
        # 1 checkout / 2 cart_adds → abandonment 50.00% = 5000 bp
        self.assertEqual(
            DailyMetric.objects.get(metric='cart_abandonment').value_int, 5000
        )

    def test_no_division_by_zero_on_empty_day(self):
        roll_daily()  # nothing seeded — must not raise
        self.assertEqual(
            DailyMetric.objects.get(metric='conversion_rate').value_int, 0
        )
```

(Import path for `Money`: match whatever `services.py` imports — check its header;
it may be `from djmoney.money import Money` or a project alias.)

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_derived_rollups -v 2`
Expected: FAIL — `DailyMetric.DoesNotExist` for `conversion_rate`.

- [ ] **Step 3: Implement the rollups**

In `services.py:roll_daily`, immediately after the `searches` upsert (~L297):

```python
    # ── Derived KPIs — rolled here so history survives the raw-event trim. ──
    # Ratios are stored as BASIS POINTS in value_int (240 = 2.40%): value_int
    # is a plain integer while value_money is currency-tagged (wrong type for
    # a ratio). aov is a true money amount → value_money.
    sessions_n = qs.values('session_id').distinct().count()
    purchases_n = rev_agg.get('n') or 0
    cart_adds_n = qs.filter(name='cart.add').count()
    checkouts_n = qs.filter(name='checkout.started').count()

    conversion_bp = round(purchases_n / sessions_n * 10_000) if sessions_n else 0
    upsert('conversion_rate', value_int=conversion_bp)

    total_rev = rev_agg.get('total')
    if total_rev is not None and purchases_n:
        upsert('aov', value_money=total_rev / purchases_n)
    else:
        upsert('aov', value_money=None)

    abandonment_bp = (
        round(max(0, cart_adds_n - checkouts_n) / cart_adds_n * 10_000) if cart_adds_n else 0
    )
    upsert('cart_abandonment', value_int=abandonment_bp)
```

- [ ] **Step 4: Add the Cohorts nav entry**

In `plugin.py:contribute_dashboard_pages`, append after the Funnel entry:

```python
            DashboardPage(
                label='Cohorts',
                slug='cohorts',
                view='plugins.installed.analytics.views.cohort_view',
                icon='users',
                section='analytics',
                order=40,
            ),
```

- [ ] **Step 5: Run to verify**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics -v 1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/analytics/
git commit -m "feat(analytics): derived daily KPIs (conversion/aov/abandonment) + Cohorts in dashboard nav"
```

---

### Task 7: Dashboard-home presence — KPIs + activity feed

**Files:**
- Create: `plugins/installed/analytics/dashboard.py`
- Modify: `plugins/installed/analytics/plugin.py:ready()`
- Test: `plugins/installed/analytics/tests/test_home_contributions.py` (create)

**Interfaces:**
- Consumes: `DailyMetric` rows incl. `conversion_rate` (Task 6), `top_sources` (existing, dimensions like `ai:chatgpt`), `AnalyticsEvent` rows `name='analytics.anomaly'` (Task 8 — feed renders empty until then).
- Produces: `on_dashboard_kpis(value, date_range=None, **kwargs)` and `on_activity_feed(value, limit=20, **kwargs)` in `analytics/dashboard.py`, registered on `events.DASHBOARD_KPIS` / `events.ACTIVITY_FEED`.
- Deviation from spec (documented): third KPI is **AI-referred sessions (7d)** from the existing `top_sources` rollup, not "AI-referred revenue" — revenue-by-source needs a raw event scan per home render; the rollup read is indexed and cheap.

- [ ] **Step 1: Write the failing test**

```python
# plugins/installed/analytics/tests/test_home_contributions.py
"""Dashboard-home KPI + activity contributions — hook-bus filters, so a
disabled analytics plugin contributes nothing (disable-safety for free)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric


class HomeKpiTests(TestCase):
    def test_kpis_appended(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        DailyMetric.objects.create(day=yesterday, metric='sessions', value_int=42)
        DailyMetric.objects.create(
            day=yesterday, metric='conversion_rate', value_int=240
        )
        kpis = hook_registry.filter(MorpheusEvents.DASHBOARD_KPIS, value=[])
        labels = {k['label'] for k in kpis}
        self.assertIn('Sessions', labels)
        self.assertIn('Conversion rate', labels)
        conv = next(k for k in kpis if k['label'] == 'Conversion rate')
        self.assertEqual(conv['value'], '2.40%')

    def test_activity_feed_surfaces_anomalies(self):
        AnalyticsEvent.objects.create(
            name='analytics.anomaly',
            kind='custom',
            payload={'metric': 'revenue', 'direction': 'down', 'z': 3.4},
        )
        items = hook_registry.filter(MorpheusEvents.ACTIVITY_FEED, value=[], limit=20)
        self.assertTrue(any(i.get('kind') == 'anomaly' for i in items))
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_home_contributions -v 2`
Expected: FAIL — no KPI with label 'Sessions' (nothing registered).

- [ ] **Step 3: Implement `dashboard.py`**

```python
# plugins/installed/analytics/dashboard.py
"""Dashboard-home contributions (DASHBOARD_KPIS / ACTIVITY_FEED filters).

Everything reads DailyMetric / recent AnalyticsEvent rows — indexed, cheap,
no raw event scans on the home render. Registered from plugin.ready(), so a
disabled plugin contributes nothing (hook bus gates on active state).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def _metric(day, name) -> int:
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    row = DailyMetric.objects.filter(day=day, metric=name, dimension='').first()
    return row.value_int if row else 0


def on_dashboard_kpis(value, date_range=None, **kwargs):
    """Sessions + conversion rate (yesterday's rollup, delta vs the day
    before) and AI-referred sessions over the trailing 7 rolled days."""
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    yday = timezone.now().date() - timedelta(days=1)
    prior = yday - timedelta(days=1)

    sessions, sessions_prior = _metric(yday, 'sessions'), _metric(prior, 'sessions')
    delta = ''
    trend = 'flat'
    if sessions_prior:
        pct = (sessions - sessions_prior) / sessions_prior * 100
        delta = f'{pct:+.0f}%'
        trend = 'up' if pct > 0 else ('down' if pct < 0 else 'flat')
    value.append(
        {
            'label': 'Sessions',
            'value': f'{sessions:,}',
            'delta': delta,
            'trend': trend,
            'icon': 'activity',
            'series': None,
            'hint': 'Consented visitor sessions yesterday (daily rollup).',
        }
    )

    conv_bp = _metric(yday, 'conversion_rate')
    conv_prior = _metric(prior, 'conversion_rate')
    conv_delta = f'{(conv_bp - conv_prior) / 100:+.2f}pp' if conv_prior else ''
    value.append(
        {
            'label': 'Conversion rate',
            'value': f'{conv_bp / 100:.2f}%',
            'delta': conv_delta,
            'trend': 'up' if conv_bp >= conv_prior else 'down',
            'icon': 'target',
            'series': None,
            'hint': 'Purchases / sessions yesterday.',
        }
    )

    week_ago = yday - timedelta(days=6)
    ai_sessions = sum(
        row.value_int
        for row in DailyMetric.objects.filter(
            day__gte=week_ago, metric='top_sources', dimension__startswith='ai:'
        )
    )
    value.append(
        {
            'label': 'AI referrals',
            'value': f'{ai_sessions:,}',
            'delta': '',
            'trend': 'flat',
            'icon': 'bot',
            'series': None,
            'hint': 'Sessions referred by AI assistants (ChatGPT, Perplexity, …), last 7 days.',
        }
    )
    return value


def on_activity_feed(value, limit=20, **kwargs):
    """Recent metric anomalies (analytics.anomaly events from the nightly
    detector) as activity items."""
    from plugins.installed.analytics.models import AnalyticsEvent  # noqa: PLC0415

    since = timezone.now() - timedelta(days=7)
    for evt in AnalyticsEvent.objects.filter(
        name='analytics.anomaly', created_at__gte=since
    ).order_by('-created_at')[:5]:
        p = evt.payload or {}
        metric = p.get('metric', 'metric')
        direction = p.get('direction', 'moved')
        value.append(
            {
                'kind': 'anomaly',
                'icon': 'alert-triangle',
                'label': f'{metric} anomaly — {direction}',
                'hint': p.get('summary', ''),
                'url': '/dashboard/analytics/v2/',
                'when': evt.created_at,
            }
        )
    return value
```

- [ ] **Step 4: Register in `plugin.py:ready()`** (after the celery-beat blocks):

```python
        # Dashboard-home presence: KPI tiles + anomaly activity — via the
        # filter bus, so a disabled plugin's tiles simply never render.
        from plugins.installed.analytics import dashboard  # noqa: PLC0415

        self.register_hook(events.DASHBOARD_KPIS, dashboard.on_dashboard_kpis, priority=30)
        self.register_hook(events.ACTIVITY_FEED, dashboard.on_activity_feed, priority=50)
```

- [ ] **Step 5: Run to verify**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics -v 1`
Expected: PASS. (If the KPI test fails because plugin hooks aren't registered in
the test env, check how `admin_dashboard/tests/test_home_modular.py` arranges
registration and mirror it.)

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/analytics/
git commit -m "feat(analytics): dashboard-home KPIs (sessions/conversion/AI referrals) + anomaly activity feed"
```

---

### Task 8: Anomaly detector v1 + nightly beat + staff notification

**Files:**
- Create: `plugins/installed/analytics/services_anomaly.py`
- Modify: `plugins/installed/analytics/tasks.py` (new task)
- Modify: `plugins/installed/analytics/plugin.py:ready()` (new beat entry)
- Test: `plugins/installed/analytics/tests/test_anomaly.py` (create)

**Interfaces:**
- Consumes: `DailyMetric` (`revenue` value_money, `orders`/`sessions`/`conversion_rate` value_int).
- Produces: `detect_anomalies(day=None) -> list[dict]` — each `{'metric', 'day', 'value', 'baseline', 'z', 'direction', 'summary'}`; records one `AnalyticsEvent(name='analytics.anomaly')` per finding (idempotent per metric+day) and calls `notify_all_staff` (fail-soft).

- [ ] **Step 1: Write the failing tests**

```python
# plugins/installed/analytics/tests/test_anomaly.py
"""Anomaly detector v1 — day-of-week robust z-score over DailyMetric.
Must fire on a seeded spike, stay quiet on flat data, and be idempotent."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric
from plugins.installed.analytics.services_anomaly import detect_anomalies


def _seed(metric: str, values: list[int]):
    """values[-1] is 'yesterday'; earlier entries step back one day each."""
    yday = timezone.now().date() - timedelta(days=1)
    for i, v in enumerate(reversed(values)):
        DailyMetric.objects.create(
            day=yday - timedelta(days=i), metric=metric, value_int=v
        )


class AnomalyTests(TestCase):
    def test_flat_data_is_quiet(self):
        _seed('orders', [10, 11, 10, 9, 10, 11, 10, 9, 10, 11, 10, 9, 10, 10])
        self.assertEqual(detect_anomalies(), [])

    def test_crash_fires(self):
        _seed('orders', [10, 11, 10, 9, 10, 11, 10, 9, 10, 11, 10, 9, 10, 0])
        findings = detect_anomalies()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['metric'], 'orders')
        self.assertEqual(findings[0]['direction'], 'down')
        self.assertTrue(
            AnalyticsEvent.objects.filter(name='analytics.anomaly').exists()
        )

    def test_idempotent_per_metric_day(self):
        _seed('orders', [10, 11, 10, 9, 10, 11, 10, 9, 10, 11, 10, 9, 10, 0])
        detect_anomalies()
        detect_anomalies()
        self.assertEqual(
            AnalyticsEvent.objects.filter(name='analytics.anomaly').count(), 1
        )

    def test_too_little_history_is_quiet(self):
        _seed('orders', [10, 0])
        self.assertEqual(detect_anomalies(), [])
```

- [ ] **Step 2: Run to verify it fails**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics.tests.test_anomaly -v 2`
Expected: FAIL — `ModuleNotFoundError: services_anomaly`.

- [ ] **Step 3: Implement `services_anomaly.py`**

```python
# plugins/installed/analytics/services_anomaly.py
"""Metric anomaly detection v1 — robust z-score against a same-weekday
baseline (falls back to trailing-14-days when history is thin). Pure
Python `statistics`, no deps; conservative defaults so it alerts on
broken-checkout-grade shifts, not noise."""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from django.utils import timezone

# metric name → how to read its value off a DailyMetric row
_WATCHED = ('revenue', 'orders', 'sessions', 'conversion_rate')
_Z_THRESHOLD = 3.0
_MIN_POINTS = 7


def _value(row) -> float:
    if row.metric == 'revenue':
        money = row.value_money
        return float(money.amount) if money is not None else 0.0
    return float(row.value_int)


def _baseline_rows(metric: str, target: date):
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    # Preferred: the same weekday over the trailing 8 weeks.
    same_weekday = [target - timedelta(weeks=w) for w in range(1, 9)]
    rows = list(
        DailyMetric.objects.filter(metric=metric, dimension='', day__in=same_weekday)
    )
    if len(rows) >= 4:
        return rows
    # Thin history: trailing 14 days.
    return list(
        DailyMetric.objects.filter(
            metric=metric,
            dimension='',
            day__gte=target - timedelta(days=14),
            day__lt=target,
        )
    )


def detect_anomalies(*, day: date | None = None) -> list[dict]:
    """Scan watched metrics for `day` (default yesterday). Returns findings
    and records one idempotent analytics.anomaly event per (metric, day);
    notifies staff fail-soft."""
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415
    from plugins.installed.analytics.services import record_event  # noqa: PLC0415

    target = day or (timezone.now().date() - timedelta(days=1))
    findings: list[dict] = []
    for metric in _WATCHED:
        today_row = DailyMetric.objects.filter(
            metric=metric, dimension='', day=target
        ).first()
        if today_row is None:
            continue
        baseline = _baseline_rows(metric, target)
        if len(baseline) < _MIN_POINTS - 1 and len(baseline) < 4:
            continue  # not enough history to judge
        values = [_value(r) for r in baseline]
        med = statistics.median(values)
        mad = statistics.median(abs(v - med) for v in values)
        # Robust sigma; guard the all-identical case with a tiny floor
        # proportional to the median so a flat-but-nonzero series with one
        # dead day still fires.
        sigma = 1.4826 * mad if mad else max(abs(med) * 0.05, 1.0)
        x = _value(today_row)
        z = (x - med) / sigma if sigma else 0.0
        if abs(z) < _Z_THRESHOLD:
            continue
        direction = 'down' if z < 0 else 'up'
        summary = (
            f'{metric} was {x:,.2f} vs a typical {med:,.2f} '
            f'(z={z:+.1f}) on {target.isoformat()}'
        )
        finding = {
            'metric': metric,
            'day': target.isoformat(),
            'value': x,
            'baseline': med,
            'z': round(z, 2),
            'direction': direction,
            'summary': summary,
        }
        findings.append(finding)

        # Idempotent event for the activity feed (max 1 per metric/day).
        record_event(
            name='analytics.anomaly',
            kind='custom',
            payload=finding,
            idempotency_key=f'anomaly:{metric}:{target.isoformat()}',
        )

    if findings:
        _notify(findings)
    return findings


def _notify(findings: list[dict]) -> None:
    """Staff notification via notifications_center — best-effort."""
    try:
        from plugins.installed.notifications_center.services import (  # noqa: PLC0415
            notify_all_staff,
        )
    except ImportError:
        return
    try:
        titles = ', '.join(f['metric'] for f in findings)
        notify_all_staff(
            kind='analytics.anomaly',
            title=f'Metric anomaly: {titles}',
            body='\n'.join(f['summary'] for f in findings),
            action_url='/dashboard/analytics/v2/',
            icon='alert-triangle',
        )
    except Exception:  # noqa: BLE001, S110 — alerting must never crash the beat
        pass
```

Note for the idempotency test: `record_event` dedupes via
`AnalyticsEvent.objects.filter(idempotency_key=…).exists()` — the second
`detect_anomalies()` call still *returns* the finding but must not create a
second event row. If the test's `findings` assertion conflicts, assert on the
event count only (as written).

- [ ] **Step 4: Beat + task**

`tasks.py` — append:

```python
@app.task(name='analytics.detect_anomalies', ignore_result=True, time_limit=120)
def detect_anomalies_task() -> int:
    from plugins.installed.analytics.services_anomaly import detect_anomalies

    findings = detect_anomalies()
    if findings:
        logger.info('analytics: %d metric anomalies detected', len(findings))
    return len(findings)
```

`plugin.py:ready()` — after the trim beat entry:

```python
        self.register_celery_beat(
            'analytics:detect_anomalies',
            {
                'task': 'analytics.detect_anomalies',
                'schedule': 60 * 60 * 24,  # daily, after roll_daily has run
            },
        )
```

- [ ] **Step 5: Run to verify**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics -v 1`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/installed/analytics/
git commit -m "feat(analytics): anomaly detection v1 — day-of-week robust z-score, nightly beat, staff alerts"
```

---

### Task 9: Full verification + E2E

**Files:** none new (fixes only if verification finds regressions)

- [ ] **Step 1: Full test sweep**

Run: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.analytics plugins.installed.storefront plugins.installed.admin_dashboard -v 1`
Expected: all green (admin_dashboard included because home KPI filters changed).

- [ ] **Step 2: Ruff + system check**

```bash
ruff check plugins/installed/analytics/ plugins/installed/storefront/views/
DATABASE_URL='sqlite:///:memory:' python manage.py check
DATABASE_URL='sqlite:///:memory:' python manage.py makemigrations --check --dry-run
```
Expected: clean / "System check identified no issues" / "No changes detected" (zero-migration promise).

- [ ] **Step 3: No-JS E2E against a local server**

```bash
DATABASE_URL='sqlite:///dev_smoke.sqlite3' DEBUG=True ALLOWED_HOSTS='localhost,127.0.0.1' \
  python manage.py runserver 8931 --noreload &
sleep 5
# consented visitor, no JS: PDP + search via curl
curl -s -b 'cookie_consent=true' http://127.0.0.1:8931/products/ -o /dev/null
PROD=$(curl -s -b 'cookie_consent=true' http://127.0.0.1:8931/products/ | grep -oE '/products/[a-z0-9-]+/' | grep -v '/products/$' | head -1)
curl -s -b 'cookie_consent=true' "http://127.0.0.1:8931${PROD}" -o /dev/null
curl -s -b 'cookie_consent=true' "http://127.0.0.1:8931/search/?q=book&mode=semantic" -o /dev/null
```

Then check events landed server-side:

```bash
DATABASE_URL='sqlite:///dev_smoke.sqlite3' python manage.py shell -c "
from plugins.installed.analytics.models import AnalyticsEvent
print('product.viewed:', AnalyticsEvent.objects.filter(name='product.viewed').count())
print('search.performed:', AnalyticsEvent.objects.filter(name='search.performed').count())
"
```
Expected: both ≥ 1 (JS never ran — server truth). Note: the `smoke-book` PDP 500s
on a pre-existing GraphQL int-overflow — use a different product if the count is 0.

- [ ] **Step 4: Dashboard smoke (browser)**

Log into `/dashboard/` (smoke@test.local / smoke12345): home shows the three new
KPI tiles; `/dashboard/analytics/v2/funnel/` renders 200 with drop-off rows;
Cohorts appears in the analytics nav.

- [ ] **Step 5: Final commit (leftovers) — do NOT push**

```bash
git status  # only intended files
git add -A plugins/installed/analytics/ plugins/installed/storefront/
git commit -m "test(analytics): slice-1 verification fixes" # only if anything changed
```

Push happens only on the user's explicit "ship" (push-to-main deploys prod).
