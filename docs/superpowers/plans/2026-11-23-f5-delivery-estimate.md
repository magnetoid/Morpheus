# F5 Delivery Estimate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a business-day delivery range under each shipping choice at checkout. Stamp the chosen rate's range on the order when it is placed, and show that stamp on the order pages and in the placed email.

**Architecture:**
- **shipping** computes the range: the handling days from `seo_graph.handling_days()` plus the rate's transit days, read by the `_transit_days` rule. It hands the range out in two places:
  - on each rate dict of its `CHECKOUT_SHIPPING_RATES` answer;
  - in the cart breakdown `meta['delivery_estimate']`.
- **orders** copies the meta into `Order.metadata['delivery_estimate']` and exposes it as `Order.delivery_estimate`.
- **core** gets one presentation filter, `business_days`, so themes and the email print the same words. No theme or shell imports shipping.

**Tech Stack:** Django 6.1 templates, gettext/ngettext (sr, hr catalogues in `locale/`), the hook bus.

**Spec:** `docs/superpowers/specs/2026-11-23-f5-delivery-estimate-design.md`

## Global Constraints

- **The setting.** `show_delivery_estimate` is a shipping setting, default off. While it is off, nothing is shown and nothing is stamped.
- **The rule.** Range = handling + transit, low end with low end and high end with high end.
  - A lone min or max stands for both ends.
  - With no handling time set, the range is transit only.
  - A rate with no transit days shows nothing.
  - Equal ends print "3 business days".
- **Wording.** English is "3–7 business days", with an en dash. It is translated for sr and hr.
- **No dates.** No calendar dates, no wallet-sheet text and no change to the structured data.
- **Boundaries.** A theme or the storefront shell never imports shipping. Orders imports no shipping code.
- **The promise is fixed.** An order shows its stamp, never a recomputation from the current rate.
- **Tests.** Assert on the marker attribute `data-delivery-estimate`, never on a bare display word.
- **Release.** Patch: `python manage.py release --patch …`.

## Review Focus

1. **Free shipping.** A coupon makes shipping free (`meta['free_shipping']`). The estimate must still stamp, because the parcel still travels. Covered by a Task 2 test.
2. **Stored values that are not usable numbers.** Strings, negatives, or max < min can arrive from a hand-edited config or old metadata. The stamp and the filter must drop them silently instead of raising on the email path. Covered by tests in Tasks 1 and 3.
3. **Setting switched off after the order was placed.** The order still shows its stamp: it is a record of what was promised. Covered by a Task 3 test.
4. **Download-only order (no shipping step).** No rate is chosen, so nothing is stamped and nothing renders. Covered by a Task 3 test (no meta, no key).
5. **Fallback rates.** When no zone matches, checkout's fallback rate "Standard delivery" (`storefront/views/checkout.py:275`) has no `estimate` key, and templates must render without error. Covered by Task 4: every template guards with `{% if r.estimate %}`.

---

### Task 1: The `business_days` filter (core)

**Files:**
- Modify: `core/templatetags/morph.py` (add the filter next to `first_sentence`)
- Modify: `locale/sr/LC_MESSAGES/django.po`, `locale/hr/LC_MESSAGES/django.po` and both compiled `.mo` files
- Test: `core/tests/test_business_days_filter.py`

**Interfaces:**
- Produces: the filter `business_days(value) -> str` in the `morph` library. `value` is a dict `{'min': int, 'max': int}` or anything else. It returns `''` for anything unusable: None, a missing key, a non-int, a negative, or max < min.

- [ ] **Step 1: Write the failing tests**

```python
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

def render(value):
    return Template('{% load morph %}{{ v|business_days }}').render(Context({'v': value}))

class BusinessDaysTests(SimpleTestCase):
    def test_a_range(self):
        self.assertEqual(render({'min': 3, 'max': 7}), '3–7 business days')
    def test_equal_ends(self):
        self.assertEqual(render({'min': 3, 'max': 3}), '3 business days')
    def test_one_day(self):
        self.assertEqual(render({'min': 1, 'max': 1}), '1 business day')
    def test_unusable_values_print_nothing(self):
        for v in (None, {}, {'min': 'x', 'max': 2}, {'min': -1, 'max': 2}, {'min': 5, 'max': 2}, 'abc'):
            self.assertEqual(render(v), '', v)
    def test_serbian_and_croatian(self):
        for lang in ('sr', 'hr'):
            with translation.override(lang):
                out = render({'min': 3, 'max': 7})
            self.assertIn('3–7', out)
            self.assertNotIn('business', out)
```

- [ ] **Step 2: Run them and see them fail**

Run: `DEBUG=True DATABASE_URL='sqlite:///:memory:' SECRET_KEY=test-key REDIS_URL=redis://127.0.0.1:6379/15 .venv/bin/python manage.py test core.tests.test_business_days_filter`
Expected: FAIL (`Invalid filter: 'business_days'`).

- [ ] **Step 3: Implement the filter**

Use `ngettext('%(min)s–%(max)s business day', '%(min)s–%(max)s business days', max)` for a range and `ngettext('%(n)s business day', '%(n)s business days', n)` for equal ends. Use `bool`/int checks so `True` is not accepted.

Add the sr entries (Latin: "%(min)s–%(max)s radni dan"/"radna dana"/"radnih dana" with the catalogue's plural forms) and the hr entries (same pattern). Then run `.venv/bin/python manage.py compilemessages -l sr -l hr`.

Ruling: the phrase lives in core so shipping's checkout text and orders' stamp print identical words without one app importing the other.

- [ ] **Step 4: Run the tests; they pass**

Same command. Expected: OK (5 tests).

- [ ] **Step 5: Commit** the filter, the tests, and both `.po` and `.mo` pairs: `feat: business_days filter for delivery ranges`.

### Task 2: Shipping computes and hands out the range

**Files:**
- Modify:
  - `plugins/installed/shipping/seo_graph.py` (the transit rule becomes one helper; add `delivery_estimate`);
  - `plugins/installed/shipping/app.py` (`get_config_schema`, `on_checkout_rates`, `on_cart_breakdown`);
  - `plugins/installed/shipping/dashboard.py` (save the checkbox);
  - `plugins/installed/shipping/templates/shipping/dashboard/shipping.html` (the checkbox next to the handling time, `id="f-shipping-show_delivery_estimate"`).
- Test: `plugins/installed/shipping/tests/test_delivery_estimate.py`

**Interfaces:**
- Produces:
  - `seo_graph.delivery_estimate(days_min, days_max) -> dict | None`, returning `{'min': int, 'max': int}`, or `None` when the rate has no transit days;
  - `seo_graph.estimate_shown() -> bool`, which reads `_shipping_config().get('show_delivery_estimate')`;
  - the rate dict key `'estimate'` (the dict above, present only when shown and computable);
  - the breakdown `meta['delivery_estimate']` (same dict, same conditions).
- `_transit_days(rate)` keeps its result. It now calls a shared `_span(lo, hi) -> tuple[int, int] | None` that `delivery_estimate` also uses.

- [ ] **Step 1: Write the failing tests** (one zone, one flat rate with `estimated_days_min=2, estimated_days_max=4`, handling 1–2 stored through `PluginConfig` the way `dashboard.py` stores it):
  - `test_off_by_default_no_estimate_anywhere`: `on_checkout_rates` dicts have no `'estimate'`, and the breakdown meta has no `'delivery_estimate'`.
  - `test_on_adds_handling_plus_transit`: `{'min': 3, 'max': 6}` on the rate dict and in the breakdown meta for that `shipping_rate_id`.
  - `test_no_handling_is_transit_only`: `{'min': 2, 'max': 4}`.
  - `test_lone_max_stands_for_both`: only `estimated_days_max=5`, no handling → `{'min': 5, 'max': 5}`.
  - `test_rate_without_days_has_none`: no `'estimate'` key, no meta key.
  - `test_free_shipping_still_stamps`: with `meta={'free_shipping': True}` going in, shipping is 0 and `meta['delivery_estimate']` is set.
  - `test_matches_the_graph`: for the same rate, `delivery_estimate`'s transit part equals `_transit_days(rate)`, and the handling part equals `handling_days()`.
  - `test_setting_is_declared_and_agent_writable`: `config_schema.properties(shipping_app)['show_delivery_estimate']['type'] == 'boolean'`, the default is False, and `config_schema.agent_writable(...)` is True.
  - `test_shipping_page_saves_the_box`: a staff POST to the Shipping page's settings form with `show_delivery_estimate=on` stores True, and a POST without it stores False. Mirror the existing handling-time save test in `shipping/tests/` for the URL and fields.

- [ ] **Step 2: Run them; they fail**

Run: `… manage.py test plugins.installed.shipping.tests.test_delivery_estimate`
Expected: FAIL (attribute and key errors).

- [ ] **Step 3: Implement**
  - In `on_cart_breakdown`, set the meta from the `quote` dict's `estimated_days_min/max` before the free-shipping branch.
  - In `on_checkout_rates`, set it from `r['estimated_days_min'/'max']` in `list_available_rates`' output.
  - `get_config_schema` returns `{'type': 'object', 'properties': {'show_delivery_estimate': {'type': 'boolean', 'default': False, 'title': 'Show delivery estimate at checkout', 'description': …}}}`.
  - Extend the `shipping.list_zones` description to name `show_delivery_estimate`, so Linda knows to use `settings.set`.

- [ ] **Step 4: Run the tests; they pass.** Then run the whole shipping app, `core.tests.test_settings_keys_have_readers` and `plugins.installed.admin_dashboard.tests.test_disable_guards`. Expected: OK.

- [ ] **Step 5: Commit**: `feat(shipping): delivery estimate on rates and in the breakdown`.

### Task 3: Orders stamps the range

**Files:**
- Modify:
  - `plugins/installed/orders/services.py` (`_order_metadata`, after the `tax_included` block);
  - `plugins/installed/orders/models.py` (property `delivery_estimate` next to `tax_included_lines`).
- Test: `plugins/installed/orders/tests/test_delivery_estimate_stamp.py`

**Interfaces:**
- Consumes: the breakdown `meta['delivery_estimate']` from Task 2.
- Produces:
  - `Order.metadata['delivery_estimate'] = {'min': int, 'max': int}`, written only when valid;
  - `Order.delivery_estimate -> dict | None`, re-validated on read.

- [ ] **Step 1: Write the failing tests**
  - `test_valid_meta_is_stamped`: `_order_metadata('', {'meta': {'delivery_estimate': {'min': 3, 'max': 6}}})['delivery_estimate'] == {'min': 3, 'max': 6}`.
  - `test_invalid_meta_is_dropped`: for `{'min': 'x'}`, `{'min': 4, 'max': 2}`, `{'min': -1, 'max': 2}` and `'3-6'`, the key is absent.
  - `test_no_meta_no_key`: covers the download-only order.
  - `test_property_reads_the_stamp_even_with_the_setting_off`: an Order saved with the stamp returns it from `.delivery_estimate`. An Order with garbage in metadata returns None.
  - `test_end_to_end_from_cart`: with shipping's setting on, `OrderService.create_from_cart` on a cart that has `metadata['shipping_rate_id']` set to a rate with days stamps the order. Mirror an existing `create_from_cart` test in `orders/tests/` for setup.

- [ ] **Step 2: Run them; they fail.**

Run: `… manage.py test plugins.installed.orders.tests.test_delivery_estimate_stamp`

- [ ] **Step 3: Implement** with one validation helper, `_estimate(value) -> dict | None`, in `orders/models.py`. `_order_metadata` uses it too, so the two can't drift. Ints only (not bool), `0 <= min <= max <= 365`.

- [ ] **Step 4: Run the tests and `plugins.installed.orders`; they pass.**

- [ ] **Step 5: Commit**: `feat(orders): stamp the delivery estimate on the order`.

### Task 4: Every theme and the placed email show it

**Files:**
- Modify, for each of `dot_books`, `supernatural_shop`, `irving_survival`, `dawnchild`, `montenegro`, `croatia`, under `themes/library/<t>/templates/storefront/`:
  - `checkout_shipping.html` and `checkout_one_page.html`: under each rate's label, `{% if r.estimate %}<span class="meta" data-delivery-estimate>{{ r.estimate|business_days }}</span>{% endif %}`, styled like the theme's existing small text;
  - `account_order_detail.html` and `order_confirmation.html`: beside the shipping method line, or after the address if the page has no method line, `{% if order.delivery_estimate %}<p data-delivery-estimate>{% trans "Estimated delivery" %}: {{ order.delivery_estimate|business_days }}</p>{% endif %}`.
- Modify: `core/emails/templates/emails/order_placed.html` and `order_placed.txt` (the same line, after the totals).
- Add "Estimated delivery" to sr and hr, then compile.
- Test: `themes/test_delivery_estimate.py`

**Interfaces:**
- Consumes: `r.estimate` (Task 2), `Order.delivery_estimate` (Task 3), `|business_days` (Task 1).

- [ ] **Step 1: Write the failing tests.** Follow `themes/test_checkout_short_form.py` for setup: the THEMES list with montenegro and croatia only when `booking_marketplace` is installed, `theme_registry` switching with cleanups, a shipping zone for the address country, and a product.
  - `test_both_checkout_forms_show_the_range_under_every_theme`: with the setting on and a rate with days 2–4, GET `/checkout/quick/` and the three-step shipping step. The rendered page contains `data-delivery-estimate` and `2–4 business days`.
  - `test_nothing_while_off`: same, setting off → no `data-delivery-estimate`.
  - `test_order_pages_show_the_stamp`: an order whose metadata carries `{'min': 3, 'max': 6}`. Its confirmation page and its account detail page (as its customer) show `data-delivery-estimate` and `3–6 business days` under every theme. An order without a stamp shows no marker.
  - `test_placed_email_html_and_text`: rendering `emails/order_placed.html` and `.txt` with that order contains `3–6 business days`. Without the stamp it does not contain "Estimated delivery".

- [ ] **Step 2: Run; they fail.** `… manage.py test themes.test_delivery_estimate`. Also run it with `MORPHEUS_EXTRA_APPS=plugins.installed.booking_marketplace` so montenegro and croatia run too.

- [ ] **Step 3: Edit the 24 theme templates and the 2 email templates.** Compile every changed template with `get_template()`, because `{% load morph %}` and `{% load i18n %}` must be present in each.

- [ ] **Step 4: Run both test runs; they pass.** Then run `themes` and `plugins.installed.storefront` (serial).

- [ ] **Step 5: Commit**: `feat(themes): show the delivery estimate at checkout, on order pages and in the email`.

### Task 5: Help, plan row, release

**Files:**
- Modify:
  - `plugins/installed/shipping/help.md`: one short paragraph on the switch and where the range shows. Use the `field:show_delivery_estimate` marker if the release_notes help tests accept it, else `settings:shipping`. Keep within its word cap.
  - `docs/plans/platform-gap-analysis-2026-11.md`: the F5 row status becomes "shipped v0.190.1".
- Release: `python manage.py release --patch "Delivery estimate at checkout" -m "…"` (writes `MORPHEUS_VERSION` and `docs/RELEASE_NOTES.md`).

- [ ] **Step 1:** Edit help.md. Run `… manage.py test plugins.installed.release_notes`. Expected: OK.
- [ ] **Step 2:** Gates:
  - `uvx ruff@0.15.8 check . && uvx ruff@0.15.8 format --check .`
  - `manage.py check` and `makemigrations --check --dry-run` (expected: no migration)
  - the three boundary and standard scripts
  - `release --check`
- [ ] **Step 3:** Full serial suite with the five opt-in apps in the background. Expected: no new failures. The known `test_beat_schedule` and `test_celery_wiring` failures appear only without the opt-in apps.
- [ ] **Step 4:** Run the release command, then commit the release with the docs: `chore: release v0.190.1 — delivery estimate at checkout`.
