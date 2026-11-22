# C4 Returns and Exchanges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A customer, signed in or a guest, returns or exchanges the goods they may send back.
They pick a refund, store credit, or another edition of the same product. They get an email at
each step, and the merchant closes the return by the outcome chosen.

**Architecture:**
- **`orders`** owns the record and the money:
  - which lines may come back (`orders/returns.py`);
  - closing a return, including building the exchange order (`orders/exchange.py`,
    `ReturnService.close`).
- **`returns_portal`** owns what the customer sees: pages, emails, settings, the chosen
  outcome (`ReturnResolution`). It takes over the customer pages from the storefront shell.
- **The dashboard** reads the chosen outcome through one new filter, `RETURN_RESOLUTION`, and
  never imports returns_portal.

**Tech Stack:** Django 6.1, django-money, Django templates, the `core.hooks` bus, unittest
(`manage.py test`).

**Spec:** `docs/superpowers/specs/2026-11-22-c4-returns-and-exchanges-design.md`

## Global Constraints

- **Tests** always pin an in-memory database:
  `DEBUG=True DATABASE_URL='sqlite:///:memory:' SECRET_KEY=test-key REDIS_URL=redis://127.0.0.1:6379/15 .venv/bin/python manage.py test <label>`.
- **Lint** with `uvx ruff@0.15.8 check` and `uvx ruff@0.15.8 format --check`. Never use the
  global ruff.
- **Imports:**
  - no import from `plugins.installed.returns_portal` in `orders`, `admin_dashboard`, `storefront`
    or a theme;
  - `returns_portal` may import `orders`, and `payments` once it is added to its `requires`.
- **Money:**
  - every amount is in the order's currency;
  - nothing refunds more than `_compute_refund` allows;
  - a fee never makes an amount negative.
- **Defaults:**
  - `exchange_fee='free'`, `exchange_fee_amount=0`, `return_instructions=''`;
  - the window is `return_window_days` (default 30);
  - store credit is offered only with `refund_store_credit`, exchange only with
    `refund_exchange`, and a refund always.
- **Exchange order events:** a free exchange order never fires `ORDER_PLACED` or
  `ORDER_PAID`. A charged one fires `ORDER_PAID` only when the customer pays it through
  `/pay/<public_token>/`.
- **Copy:** all customer-facing text is `{% translate %}` / `gettext`, in plain words, and
  says "store credit", "exchange", "refund".
- **Assertions:** test on a unique marker (slug, RMA number, `data-` attribute), never a bare
  display word (CLAUDE.md).
- **Every changed template** compiles with `get_template()`.
- **Release:** `manage.py release --minor "Customers can return and exchange on their own" -m …`
  (v0.188.0) in the last task.

## Review Focus

1. **Two returns racing for the last unit.** Two tabs each ask to return the one unit; the
   second is refused. Test: `test_second_request_for_the_last_unit_is_refused` (Task 1).
2. **A guest with someone else's order number.** Number plus the wrong email shows the same
   "check your details" page as an unknown number. Test:
   `test_wrong_email_reads_like_an_unknown_order` (Task 4).
3. **Charged exchange never paid.** The deadline sweep cancels the exchange order, and the
   return then closes as a refund. Test: `test_cancelled_unpaid_exchange_refunds_the_return`
   (Task 5).
4. **Edition sold out between request and receipt.** That line is refunded, and the email
   names it. Test: `test_sold_out_edition_is_refunded_instead` (Task 2).
5. **returns_portal switched off.** The order page, the account tile, the email link and the
   paths are all gone, and the dashboard offers refund and credit only. Tests:
   `test_disabled_app_leaves_no_return_surface` (Task 4) and
   `test_without_portal_no_exchange_is_offered` (Task 6).

---

### Task 1: Which lines may come back

**Files:**
- Create: `plugins/installed/orders/returns.py`
- Modify: `plugins/installed/orders/refunds.py` (`ReturnService.create_request`)
- Test: `plugins/installed/orders/tests/test_returnable_lines.py`

**Interfaces:**
- Produces:
  - `ReturnableLine` (frozen dataclass): `item: OrderItem`, `units: int` (units that may
    still come back), `reason: str` (`''` when `units > 0`, else one of `'not_paid'`,
    `'not_sent'`, `'does_not_ship'`, `'window_closed'`, `'already_returned'`,
    `'exchange_order'`), `window_ends: date | None`.
  - `returnable_lines(order, *, window_days: int, today: date | None = None) -> list[ReturnableLine]`.
  - `parcel_start(fulfillment) -> datetime`: the parcel's `delivered_at`, else
    `shipped_at or created_at` plus `orders.withdrawal.TRANSIT_ALLOWANCE_DAYS`.
  - `ReturnRefused(ValueError)`.
  - `ReturnService.create_request(..., window_days: int | None = None)`: when `window_days`
    is given, it locks the order (`select_for_update`) and raises `ReturnRefused` if any
    requested `(order_item_id, quantity)` exceeds `returnable_lines(...)` units. With `None`
    (staff and withdrawal callers), behaviour is unchanged.

**Rules for a line's units:**
- **Paid:** `order.payment_status in ('paid', 'partially_refunded')`.
- **Ships:** `line_ships(item)` is true; a download or service never can.
- **Sent:** the units are in `FulfillmentItem` rows.
- **Window:** each parcel's units stay returnable until `parcel_start(parcel).date() + window_days`.
  A unit belongs to the earliest parcel holding it.
- **Not already held:** subtract the units in every `ReturnRequest` of this order whose state
  is not `rejected` or `cancelled`.
- **Not an exchange:** an order whose `metadata` has `exchange_of` has no returnable units.
- **No window:** `window_days <= 0` means nothing is returnable (`'window_closed'`).

- [ ] **Step 1: Write the failing tests**

Names:
- `test_unpaid_order_has_nothing_to_return`
- `test_download_line_never_returns`
- `test_unsent_units_are_not_returnable_but_sent_ones_are` (2 units, 1 in a parcel → units 1)
- `test_window_counts_from_the_parcels_delivery` (delivered 10 days ago, window 7 →
  `'window_closed'`; window 30 → returnable, `window_ends == delivered + 30d`)
- `test_parcel_without_delivery_gets_the_transit_allowance`
- `test_units_in_an_open_return_are_held`
- `test_rejected_return_releases_its_units`
- `test_exchange_order_is_not_returnable`
- `test_second_request_for_the_last_unit_is_refused`: two `create_request(window_days=30)`
  calls for the same one unit; the second raises `ReturnRefused`.
- `test_staff_request_without_window_is_unchanged`

Build orders as `returns_portal/tests/test_withdrawal.py:_order` does, then add a `Fulfillment`
and `FulfillmentItem`.

- [ ] **Step 2: Run them and watch them fail**

Run: `… manage.py test plugins.installed.orders.tests.test_returnable_lines`
Expected: ImportError (no module `orders.returns`).

- [ ] **Step 3: Implement `orders/returns.py` and the `create_request` guard**

The guard runs the check and the insert in one `transaction.atomic()`, with the order row
locked first.

- [ ] **Step 4: Run the tests and the orders suite**

Run: `… manage.py test plugins.installed.orders`
Expected: all OK.

- [ ] **Step 5: Commit**

`git commit -m "feat(orders): which order lines may be returned, and refusing more"`

---

### Task 2: Closing a return, with the exchange order

**Files:**
- Create: `plugins/installed/orders/exchange.py`
- Modify: `plugins/installed/orders/refunds.py` (add `ReturnService.close`; keep
  `mark_received_and_refund` as a thin wrapper over `close`)
- Test: `plugins/installed/orders/tests/test_return_close.py`

**Interfaces:**
- Consumes: `ReturnRequest`, `ReturnService._compute_refund`, `services.settle_free_order`,
  `MorpheusEvents.ORDER_RESERVE_STOCK`.
- Produces:
  - `ExchangeLine` (frozen dataclass): `order_item_id: str`, `variant_id: str`,
    `quantity: int`.
  - `paid_unit_price(order_item) -> Money`: the unit list price less its prorated share of
    `order.discount_total`, the same proration `_compute_refund` uses (2 dp).
  - `create_exchange_order(rr, lines: list[ExchangeLine], *, fee: Money) -> tuple[Order | None, list[ExchangeLine]]`.
    It returns the new order and the lines it could not make.
  - `ReturnService.close(rr, *, outcome: str, actor=None, exchange: list[ExchangeLine] | None = None, fee: Money | None = None) -> ReturnRequest`.
    - `outcome` is `'refund' | 'store_credit' | 'exchange'`.
    - It sets `rr.state='refunded'` and fires `return.refunded` once, with kwargs
      `return_request`, `refund`, `store_credit`, `outcome`, `exchange_order`, `unmade`.

**Decisions:**
- **The exchange order:**
  - It copies `customer`, `email`, `shipping_address`, `billing_address` and `channel`.
  - Each line is the new variant at `paid_unit_price(returned item)`.
  - `subtotal` is the sum of the lines, `discount_total` equals that subtotal, and
    `shipping_total` is the fee, with `shipping_method='Exchange fee'` when the fee is
    above 0. `total` is the fee.
  - `metadata = {'exchange_of': rr.rma_number, 'return_id': str(rr.id)}` and `source='exchange'`.
- **Making it:**
  - Fire `ORDER_RESERVE_STOCK` (`raise_errors=True`) as `create_from_cart` does.
  - With a total of 0, call `settle_free_order(order)` and suppress its `ORDER_PAID`.
    Settle inline instead: `payment_status='paid'`, `confirm()`, save, no event.
  - With a total above 0, leave it `pending`/`unpaid`; returns_portal sends the link (Task 5).
  - Never fire `ORDER_PLACED`.
  - Write a timeline event on both orders: `EXCHANGE_CREATED` / `EXCHANGED_FOR`.
- **A line that cannot be made** (variant inactive, not for sale, different product, price
  above the paid price, or reservation refused):
  - it joins `unmade` and is refunded through the refund path;
  - if every line is unmade, the outcome becomes `'refund'`.
- **The difference** for a cheaper edition: `paid_unit_price − variant price`, never below 0,
  is refunded with `RefundService.process` (`reason='customer_request'`,
  `notes='RMA … exchange difference'`), less the fee. Whatever fee is left over goes on the
  exchange order.
- **Refund and store credit** keep today's path. A `fee` is taken off the amount, which is
  never below 0.
- **Locking:** `close` holds `select_for_update` on the return and refuses states other than
  `approved` or `received`, as today.

- [ ] **Step 1: Write the failing tests**

Names:
- `test_close_refund_matches_todays_refund`
- `test_close_store_credit_takes_off_the_fee`
- `test_fee_never_makes_a_refund_negative`
- `test_equal_price_exchange_is_a_paid_zero_order_linked_to_the_return`: asserts
  `total == 0`, `payment_status == 'paid'`, `metadata['exchange_of'] == rr.rma_number` and
  the line variant.
- `test_exchange_order_fires_no_placed_or_paid_event`: subscribe test handlers for
  `ORDER_PLACED` and `ORDER_PAID`, save and restore `_handlers` with `addCleanup`
  (CLAUDE.md landmine), and assert neither fired.
- `test_cheaper_edition_refunds_the_difference`: paid 10, new edition 7, `Refund.amount == 3`.
- `test_fee_comes_off_the_difference_first_then_goes_on_the_order`: difference 3, fee 5 →
  no refund, exchange `total == 2`, `payment_status == 'unpaid'`.
- `test_sold_out_edition_is_refunded_instead`: reservation raises, so `unmade` holds the
  line, `outcome == 'refund'` and a refund exists.
- `test_dearer_edition_is_refused`
- `test_return_refunded_fires_once_with_the_outcome`
- `test_close_twice_is_refused`

- [ ] **Step 2: Run them and watch them fail**

Run: `… manage.py test plugins.installed.orders.tests.test_return_close`
Expected: AttributeError (`ReturnService.close`).

- [ ] **Step 3: Implement `orders/exchange.py` and `ReturnService.close`**

- [ ] **Step 4: Run the orders and inventory suites**

Run: `… manage.py test plugins.installed.orders plugins.installed.inventory`
Expected: all OK. Inventory restocks once per return, via `return.refunded`.

- [ ] **Step 5: Commit**

`git commit -m "feat(orders): close a return by refund, credit or exchange order"`

---

### Task 3: Settings and the outcome a return carries

**Files:**
- Modify:
  - `plugins/installed/returns_portal/app.py` (schema: `exchange_fee` enum
    `['free','same_as_return','fixed']`, `exchange_fee_amount` number, `return_instructions`
    string with `format: textarea`; `requires` gains `'payments'`; register the
    `RETURN_RESOLUTION` hook)
  - `core/hooks.py` (document and add `MorpheusEvents.RETURN_RESOLUTION = 'return.resolution'`:
    filter, value None, kwargs `return_request`)
- Create: `plugins/installed/returns_portal/policy.py`
- Test: `plugins/installed/returns_portal/tests/test_policy.py`

**Interfaces:**
- Produces:
  - `offered_outcomes(order, *, signed_in: bool) -> list[str]`. It always contains
    `'refund'`, adds `'store_credit'` when `refund_store_credit` and `signed_in` and
    `order.customer_id`, and adds `'exchange'` when `refund_exchange`.
  - `exchange_editions(item) -> list[ProductVariant]`: the other active, `is_for_sale`
    variants of `item.product` priced at or below `paid_unit_price(item)`, excluding
    `item.variant`.
  - `return_fee(order) -> Money`: for `return_fees == 'fixed_fee'` it is
    `return_shipping_fee`, else 0.
  - `exchange_fee(order) -> Money`:
    - `free` → 0;
    - `same_as_return` → `return_fee(order)`;
    - `fixed` → `exchange_fee_amount`.
  - `on_return_resolution(value, return_request=None, **kw) -> dict | None`. It returns
    `{'outcome': str, 'exchange': [ExchangeLine…], 'fee': Money, 'label': str}` from the
    return's `ReturnResolution`, or None when there is none.
  - The fee is `exchange_fee` for an exchange and `return_fee` for the other outcomes.

- [ ] **Step 1: Write the failing tests**

Names:
- `test_refund_is_always_offered`
- `test_store_credit_needs_the_switch_and_an_account`
- `test_exchange_needs_the_switch`
- `test_editions_are_same_product_for_sale_and_not_dearer`
- `test_exchange_fee_modes`, three subtests: free=0, same_as_return with fixed_fee 4 → 4,
  fixed 6 → 6
- `test_resolution_hook_answers_from_the_portal_row`
- `test_resolution_hook_is_none_without_a_row`
- `test_settings_keys_have_readers` passes: run `core.tests.test_settings_keys_have_readers`

Use `plugins.testing.set_app_settings`.

- [ ] **Step 2: Run them and watch them fail**

Run: `… manage.py test plugins.installed.returns_portal.tests.test_policy`
Expected: ImportError.

- [ ] **Step 3: Implement the schema, `policy.py` and the hook**

- [ ] **Step 4: Run returns_portal and core settings guards**

Run: `… manage.py test plugins.installed.returns_portal core.tests.test_settings_keys_have_readers`
Expected: OK.

- [ ] **Step 5: Commit**

`git commit -m "feat(returns_portal): exchange fee, return instructions, offered outcomes"`

---

### Task 4: The customer's pages move into returns_portal

**Files:**
- Create:
  - `plugins/installed/returns_portal/views_returns.py`
  - `plugins/installed/returns_portal/templates/returns_portal/returns_start.html` (guest)
  - `…/return_form.html`
  - `…/returns_list.html`
  - `…/return_status.html`
  - `…/blocks/order_return.html`
- Modify:
  - `plugins/installed/returns_portal/urls.py`:
    - `account/orders/<str:order_number>/return/` → `return_form` (name `return_form`);
    - `account/returns/` → `returns_list`;
    - `account/returns/<uuid:rma_id>/` → `return_status`;
    - `returns/` → `returns_start`.
    - Literals come before converters.
  - `plugins/installed/returns_portal/app.py`:
    - an `account_order_actions` block `order_return.html`;
    - `cta.html` links `/account/returns/`;
    - `ORDER_EMAIL_LINKS` adds "Return or exchange" with `?token=`.
  - `plugins/installed/storefront/views/account.py`: delete `account_returns`,
    `account_return_status` and `account_order_return`.
  - `plugins/installed/storefront/views/__init__.py` and `plugins/installed/storefront/urls.py`:
    drop the three.
  - `plugins/installed/seo/pages/resolve.py:90-95`: rename to `returns_portal:return_form`,
    `returns_portal:returns_list` and `returns_portal:return_status`.
  - `themes/library/{dot_books,dawnchild,supernatural_shop,irving_survival,montenegro,croatia}/templates/storefront/account_order_detail.html`:
    delete the hardcoded "Request a return" link; `account_order_actions` already renders.
  - The same six themes' `account_home.html`: delete the hardcoded `/account/returns/` link
    (the `account_summary_extra` tile carries it).
- Delete: the 18 theme templates `storefront/account_returns.html`,
  `account_return_status.html` and `account_order_return.html`.
- Test: `plugins/installed/returns_portal/tests/test_return_pages.py`

**Interfaces:**
- Consumes:
  - `returnable_lines`, `ReturnRefused`, `ReturnService.create_request(window_days=)` from
    Task 1;
  - `offered_outcomes`, `exchange_editions` and `exchange_fee`/`return_fee` from Task 3;
  - `orders.withdrawal.find_order`;
  - `returns_portal.views._throttled`.
- Produces: views `return_form`, `returns_list`, `return_status` and `returns_start`. A
  `ReturnResolution` row is written with each request, with `exchange_choices =
  [{order_item_id, exchange_variant_id}]`.

**Access rules:**
- **The form and the status page answer:**
  - the signed-in owner (`order.customer_id == user.pk`);
  - or a `?token=` equal to `order.public_token` (`secrets.compare_digest`), remembered in
    the session as the withdrawal pages do.
  - Anyone else gets 404.
- **`returns_start`** (POST order number + email, throttled) redirects to the form with the
  token. A wrong pair re-renders the same page with the same message as an unknown number.
- **The status page by token** lists that order's returns.

**The form:**
- It lists only `returnable_lines` with `units > 0`, and shows the reason text for the rest.
- It shows the outcome radios from `offered_outcomes`, an edition select per line when
  exchange is offered and the line has editions, and the fee that applies.
- It shows `window_ends`.
- On `ReturnRefused` it re-renders with "Those items can no longer be returned".

**Order actions block:** shown only while some line has `units > 0`.

- [ ] **Step 1: Write the failing tests**

Names:
- `test_owner_sees_the_form_with_returnable_lines_only`
- `test_guest_reaches_the_form_with_number_and_email`
- `test_wrong_email_reads_like_an_unknown_order` (identical body marker for both)
- `test_token_link_opens_the_form_and_status`
- `test_other_customer_and_wrong_token_get_404`
- `test_request_writes_the_return_and_its_resolution`
- `test_exchange_choice_must_be_an_offered_edition`
- `test_store_credit_not_offered_to_a_guest`
- `test_order_page_shows_the_action_only_when_something_can_come_back`
- `test_old_account_paths_still_answer` (`/account/returns/` → 200 for the owner)
- `test_disabled_app_leaves_no_return_surface`: toggle `returns_portal` off; the order page
  has no `data-return-action` marker, the account home has no tile, the paths 404, and the
  email links omit it.
- `test_every_theme_renders_the_pages`: loop over the six themes and render each new
  template under the theme, as `themes/test_*` do.

- [ ] **Step 2: Run them and watch them fail**

Run: `… manage.py test plugins.installed.returns_portal.tests.test_return_pages`
Expected: 404s or NoReverseMatch.

- [ ] **Step 3: Implement the views, URLs, templates and block, then delete the shell code
  and theme templates**

- [ ] **Step 4: Run storefront, returns_portal, seo and themes**

Run: `… manage.py test plugins.installed.storefront plugins.installed.returns_portal plugins.installed.seo themes`
Expected: OK. Fix any storefront test that reversed `storefront:account_returns`.

- [ ] **Step 5: Commit**

`git commit -m "feat(returns_portal): customers and guests return and exchange on their own"`

---

### Task 5: The customer's emails, and paying a charged exchange

**Files:**
- Create:
  - `plugins/installed/returns_portal/notices.py`
  - `templates/emails/return_requested.{html,txt}`
  - `return_approved.{html,txt}`
  - `return_rejected.{html,txt}`
  - `return_closed.{html,txt}`
- Modify: `plugins/installed/returns_portal/app.py` (four `EmailTemplateDef`s in group
  `Orders`; hooks `return.requested`, `return.approved`, `return.rejected`,
  `return.refunded`; `ORDER_CANCELLED`)
- Test: `plugins/installed/returns_portal/tests/test_return_emails.py`

**Interfaces:**
- Consumes: the `return.refunded` kwargs from Task 2; `payments.pay_link.send(order, kind='link')`.
- Produces:
  - `on_return_requested`, `on_return_approved`, `on_return_rejected`, `on_return_closed`
    and `on_order_cancelled` in `notices.py`.
  - Each email goes only to `order.email`, with ctx `{order, rma, lines, status_url}`, where
    `status_url` is `/account/returns/<id>/?token=<public_token>`.
  - The approval email also carries `return_instructions`, rendered with `linebreaks`.
  - The closing email names the outcome, the refund or credit amount, the exchange order
    number, and each `unmade` line.

**Decisions:**
- **A charged exchange:** `on_return_closed` with `exchange_order` and `total > 0` calls
  `pay_link.send(exchange_order, kind='link')`. The closing email says the new edition ships
  once paid.
- **The deadline:**
  - `on_order_cancelled` for an order whose `metadata` has `exchange_of` and is unpaid looks
    up the return by `metadata['return_id']`.
  - It refunds the returned lines with `RefundService.process` and writes a timeline event.
  - The return row stays `refunded` with a staff note; no second `return.refunded` fires.

- [ ] **Step 1: Write the failing tests**

Names:
- `test_request_sends_return_requested_to_the_order_email` (check `mail.outbox`, subject
  carries the RMA number)
- `test_approval_email_carries_the_instructions`
- `test_rejection_email_carries_the_staff_note`
- `test_closing_email_names_unmade_lines`
- `test_charged_exchange_sends_the_payment_link`
- `test_cancelled_unpaid_exchange_refunds_the_return`
- `test_templates_compile` (`get_template` on all eight)
- `test_disabled_app_sends_nothing`

- [ ] **Step 2: Run them and watch them fail**

Run: `… manage.py test plugins.installed.returns_portal.tests.test_return_emails`
Expected: empty outbox.

- [ ] **Step 3: Implement `notices.py`, the templates and the registrations**

- [ ] **Step 4: Run returns_portal, payments and the email-template guards**

Run: `… manage.py test plugins.installed.returns_portal plugins.installed.payments core.tests.test_core_email_templates`
Expected: OK.

- [ ] **Step 5: Commit**

`git commit -m "feat(returns_portal): return emails, and the payment link for a charged exchange"`

---

### Task 6: The dashboard closes a return by its outcome

**Files:**
- Modify:
  - `plugins/installed/admin_dashboard/views_split/returns.py` (`return_detail`)
  - `plugins/installed/admin_dashboard/templates/admin_dashboard/return_detail.html`
- Test: `plugins/installed/admin_dashboard/tests/test_return_close_form.py`

**Interfaces:**
- Consumes: the `RETURN_RESOLUTION` filter (Task 3); `ReturnService.close` and
  `ExchangeLine` (Task 2).

**Decisions:**
- **The view** asks `hook_registry.filter(MorpheusEvents.RETURN_RESOLUTION, None,
  return_request=rr)` and shows the outcome label and exchange editions.
- **The "Mark received" form** (state `approved` or `received`) has:
  - an outcome radio: refund and store credit always (credit only with a customer), exchange
    only when the resolution names one, with the resolution's outcome preselected (refund
    without one);
  - a fee amount input, prefilled with the resolution's fee and blank meaning 0;
  - a single `action=close` button.
- **The POST** calls `ReturnService.close(rr, outcome=…, actor=request.user, exchange=resolution['exchange'] if outcome=='exchange' else None, fee=Money(fee, order currency))`.
  The two old buttons go; `refund_money` and `refund_credit` POSTs map onto `close` for one
  release (old open tabs).

- [ ] **Step 1: Write the failing tests**

Names:
- `test_detail_shows_the_customers_chosen_exchange`
- `test_close_exchange_creates_the_linked_order`
- `test_staff_can_waive_the_fee`
- `test_without_portal_no_exchange_is_offered`
- `test_old_refund_buttons_still_close`
- Permission boundary: anonymous redirected; staff without `orders.write` denied under
  `enforce`.

- [ ] **Step 2: Run them and watch them fail**

Run: `… manage.py test plugins.installed.admin_dashboard.tests.test_return_close_form`
Expected: FAIL (no outcome shown).

- [ ] **Step 3: Implement the view and template changes**

- [ ] **Step 4: Run admin_dashboard, orders and the boundary scripts**

Run: `… manage.py test plugins.installed.admin_dashboard plugins.installed.orders && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_core_boundary.py`
Expected: OK, no new pair.

- [ ] **Step 5: Commit**

`git commit -m "feat(dashboard): close a return by the customer's chosen outcome"`

---

### Task 7: Docs, coverage, release

**Files:**
- Modify:
  - `plugins/installed/returns_portal/help.md`: returns and exchanges, the new fields via
    `field:` markers. It stays under the word cap; check with
    `release_notes/tests/test_help_*`.
  - `plugins/installed/orders/help.md`: one line on exchange orders.
  - `CLAUDE.md`: a convention paragraph, "a return closes by its outcome (v0.188.0)", naming
    `orders/returns.py`, `orders/exchange.py`, `RETURN_RESOLUTION`, the no-`ORDER_PLACED`
    rule and the guards.
  - `docs/plans/platform-gap-analysis-2026-11.md`: C4 row status; P9 row now "live".
  - `docs/plans/janus-alignment-and-app-platform-2026-11.md`: P9 "live".
  - `docs/PLUGIN_DEVELOPMENT.md`: the `RETURN_RESOLUTION` hook.
  - `scripts/agent_coverage_baseline.json`: new staff POST views baselined with
    `none: P10 returns batch`, via the script's `--save`.
  - `scripts/plugin_standard_baseline.json` only if the ratchet asks.
- Release: `manage.py release --minor "Customers can return and exchange on their own" -m "…" -m "…"` → v0.188.0.

- [ ] **Step 1: Write docs and run the help guards**

Run: `… manage.py test plugins.installed.release_notes`
Expected: OK.

- [ ] **Step 2: Run every CI gate**

Run: `uvx ruff@0.15.8 check . && uvx ruff@0.15.8 format --check . && .venv/bin/python manage.py check && .venv/bin/python manage.py makemigrations --check --dry-run && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py && .venv/bin/python scripts/check_agent_coverage.py`
Expected: all pass. `makemigrations` finds nothing: there are no new model fields.

- [ ] **Step 3: Run the wide suite serially (with the opt-in apps)**

Run: `MORPHEUS_EXTRA_APPS=… … manage.py test plugins.installed.orders plugins.installed.returns_portal plugins.installed.storefront plugins.installed.admin_dashboard plugins.installed.inventory plugins.installed.payments plugins.installed.seo themes core`
Expected: OK, or failures known on main named in the report.

- [ ] **Step 4: Release and commit**

Run: `.venv/bin/python manage.py release --minor "Customers can return and exchange on their own" -m … --commit`
Expected: `release --check` passes.
