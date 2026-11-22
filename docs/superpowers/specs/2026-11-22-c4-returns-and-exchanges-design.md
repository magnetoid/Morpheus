# C4: customer returns and exchanges (design)

Status: approved by the owner, 2026-11-22. Row C4 of
`docs/plans/platform-gap-analysis-2026-11.md` (order of work #8).

## Intent

A shopper should be able to return or exchange goods on their own, without writing to the
store, the way Shopify and the other platforms let them. Today they can only start a return,
and the flow has holes (below). C4 closes the holes and adds the choice of outcome and the
exchange. It is for the stores that ship goods: Supernatural, Irving, and the printed
editions on dotbooks and Dawnchild.

The owner's own words: the exchange is "same book, other edition", and the new edition goes
out "when the old one arrives". The rest is my proposal, which the owner accepted as a
whole.

## What exists today (main, v0.187.0)

- **The record** is `orders.ReturnRequest` (`orders/refunds.py`), with these states:
  `requested → approved | rejected`, then `approved → received → refunded`, plus `cancelled`.
  It has RMA numbers and `items = [{order_item_id, quantity}]`.
- **`ReturnService`** creates, approves, rejects and `mark_received_and_refund(as_store_credit=)`.
  It fires `return.requested`, `return.approved`, `return.rejected` and `return.refunded`.
  - `return.refunded` restocks through inventory.
  - Nothing listens to `return.approved` or `return.rejected`.
- **The shopper's pages live in the storefront shell** (`storefront/views/account.py`):
  - `/account/orders/<n>/return/` (a form);
  - `/account/returns/` and `/account/returns/<id>/` (status steps).
  - All six themes ship the three templates, and every order page links "Request a return".
- **Dashboard:** `admin_dashboard/views_split/returns.py` lists returns and offers approve,
  reject, received+refund and received+store credit.
- **`returns_portal`** owns:
  - the F3 withdrawal pages (guest by order number + email, or the order's `public_token`);
  - the return terms published to search engines: `return_window_days` (30),
    `return_fees` (`not_stated` / `free` / `customer_pays` / `fixed_fee`),
    `return_shipping_fee`, `refund_full`, `refund_exchange` and `refund_store_credit`;
  - two models nothing writes: `ReturnResolution` (refund / exchange / store_credit, plus
    `exchange_choices`) and `ReturnFeedback`.

**The holes:**
1. The window is published but never enforced.
2. Any order can be returned: unpaid, not yet shipped, or a download.
3. A line can be returned twice, or more units than were bought (open returns aren't counted).
4. The customer gets no email at any step.
5. There is no guest path.
6. There is no choice of outcome and no exchange.
7. Switching returns_portal off leaves the form, because it lives in the shell.

## Goals

1. A signed-in customer or a guest asks for a return of the lines that can come back. They
   pick a reason and an outcome: refund, store credit (signed-in only) or exchange.
2. A line can come back when all of these hold:
   - the order is paid;
   - the line ships and has been sent;
   - the window, counted from delivery, is still open;
   - units are left that no open or finished return already holds.

   A download or service never can.
3. **Exchange:** the same product in another active edition (variant) whose price is equal or
   lower and which is for sale.
   - When the merchant marks the goods received, a new order goes out for the new edition.
   - It costs 0 and is already paid. It is linked to the return and goes through stock,
     parcels and the "on its way" email like any order.
   - A cheaper edition's difference is refunded the usual way.
4. **Emails** to the customer:
   - request received;
   - approved, with the merchant's return instructions;
   - rejected, with the staff note;
   - closed (refund, credit or exchange sent).

   Each email links to the status page, which works for guests through the order's token.
5. **Settings**, one source with what the store publishes:
   - the window is `return_window_days`;
   - the outcomes offered come from `refund_store_credit` and `refund_exchange`; a refund is
     always offered;
   - a `fixed_fee` is taken off a refund;
   - a new `return_instructions` text (where to send it, how to pack it) goes into the
     approval email and the status page;
   - **an exchange fee the merchant sets up** (owner, 2026-11-22: "options to setup in
     backend, so it can be free or charging, depending on situation"):
     - `exchange_fee`: `free` (default) | `same_as_return` (the `return_fees` rule and amount)
       | `fixed`, with its own amount `exchange_fee_amount`;
     - staff can change it on each return at "Mark received": waive it, or set another amount;
     - the form shows the fee before the customer sends the request.
6. **The pages move into returns_portal.** Switching the app off removes the button, the
   pages and the emails. The storefront's three views and their links go.
7. **The dashboard return page** shows the customer's chosen outcome and exchange edition.
   - "Mark received" closes the return by that outcome.
   - Staff can still override: refund instead of an exchange, or credit instead.

## Non-goals

- An exchange to another product, or to a dearer edition. Collecting a price difference
  is A10b (order editing). A charged exchange fee is collected (see "Exchange fee" below),
  but no price difference is.
- Return shipping labels. Buying a carrier label for the return parcel is a follow-up; the
  instructions text covers it now.
- Approving returns automatically. The merchant approves each one, as today.
- Linda's return tools (`returns.approve/reject/receive`). They belong to P10's returns
  batch.
- `ReturnFeedback` (the "what went wrong" box). It stays unwritten.

## Anti-goals

- Replacing the store's published policy with code defaults. Whatever the form allows must
  be exactly what `return_window_days` and the refund switches tell search engines.
- Sending the new edition before the old one is received.
- Giving a guest store credit. They have no account to hold it.
- A second return record. `orders.ReturnRequest` stays the one owner;
  `ReturnResolution` extends it (CLAUDE.md, one concept one owner).

## Approaches considered

- **Chosen: the exchange is its own order, linked to the return, created by orders when the
  goods are received.** It reuses stock reservation, parcels, labels and the shipping
  emails unchanged.
- **Add the new edition to the original order.** Rejected: a paid order can't change until
  A10b, and its parcel is closed.
- **Make the exchange through `draft_orders`.** Rejected: that app is optional, so exchanges
  would vanish on a store that switches it off. Orders own orders.
- **Exchange scope** (owner, 2026-11-22): the same product in another edition, not anything
  in the store.
- **Timing** (owner): the new edition is sent when the old one arrives, not on approval.

## The how, as decided

- **orders** owns the record and the money:
  - **`orders/returns.py`, new.**
    - `returnable_lines(order, *, window_days, today=None)` gives each line with the units
      it may return and why not. It reuses `orders.withdrawal`'s delivery start (`_goods_start`
      moves into a shared helper or is imported) and `line_ships`.
    - `ReturnService.create_request` refuses lines and units that `returnable_lines` does not
      allow, under a lock on the order, so two tabs cannot both return the last unit.
  - **`orders/exchange.py`, new.**
    - `create_exchange_order(rr, choices)` copies the customer, email and addresses. It adds
      each new edition at the price paid for the returned line and fires the same stock
      reservation gate as checkout, settled with `settle_free_order`.
    - `metadata['exchange_of'] = rma_number`, and a timeline event is written on both orders.
    - A line whose edition is gone or out of stock when the goods arrive is refunded instead,
      and the return says so.
  - **`ReturnService.close(rr, *, outcome, actor)`** replaces the dashboard's two received
    buttons:
    - `refund` keeps today's path;
    - `store_credit` keeps today's path;
    - `exchange` creates the exchange order and refunds any difference.

    It fires `return.refunded` in every case, so inventory restocks once. The fixed fee is
    taken off a refund or credit amount and never makes it negative.
- **returns_portal** owns what the customer sees:
  - **Pages** under `/returns/`:
    - start: a guest gives order number + email (`find_order`), or arrives by the order
      link's token;
    - the form: lines and units from `returnable_lines`, reason, outcome, and for an
      exchange each line's editions;
    - sent;
    - the status page for one return, signed-in or by token.
  - The account list of returns moves too.
  - **Links come from contributions:**
    - the order page's action comes through the existing `account_order_actions` block, shown
      only when a line can come back;
    - the order email link comes through `ORDER_EMAIL_LINKS`;
    - the account tile comes through `account_summary_extra`.
  - Themes keep only styling: the six themes' three templates are replaced by returns_portal
    templates that render inside each theme's base. Each theme that needs it gets a
    theme-level override, as the withdrawal pages do today.
  - It writes `ReturnResolution` with the choice.
  - It listens to `return.requested`, `.approved`, `.rejected` and `.refunded` to send the
    four emails. They are contributed email templates the merchant can edit, sent only to
    the order's email.
  - It adds `return_instructions` to its settings schema, with its reader in the same change.
- **Dashboard:** the return detail page shows the chosen outcome and editions, and a "Mark
  received" form with the outcome preselected. It stays in admin_dashboard, which already
  imports orders' ReturnService; the outcome display reads `ReturnResolution` through a
  `RETURN_DETAIL_PANELS`-style hook rather than an import.
- **Agent tools:** P10 adds Linda's tools. C4 lists the new customer and merchant actions in
  the agent-coverage baseline with the reason "P10 returns batch". This follows the P8 rule:
  `none:` never means "not built yet", so they stay baselined.
- **Release:** `manage.py release --minor` (v0.188.0), with help.md for returns_portal and
  orders updated, and CLAUDE.md gaining a convention paragraph.

## Answers to the builder check (2026-11-22)

Each answer below marked "my call" is mine, for the owner to check.

1. **Partly shipped orders (my call).** A line counts per parcel.
   - Once a line's units are in a parcel, they can come back while other lines are still open.
   - Their window starts at that parcel's `delivered_at`. Without a delivery date, it starts at
     `shipped_at` plus `TRANSIT_ALLOWANCE_DAYS`, the same allowance withdrawals use, so what
     search engines are told stays true.
   - This needs a per-parcel helper beside `_goods_start`; the withdrawal rule stays
     order-level, as the law has it.
2. **Exchange order money (my call).**
   - Each new line is priced at what the customer paid for the returned unit: list price less
     its prorated share of the order's discount, the same sum as `_compute_refund`.
   - That whole amount is the exchange order's discount, so the total is 0.
   - It never fires `ORDER_PLACED` or `ORDER_PAID`. Otherwise GA4, the ad conversion APIs,
     loyalty points, affiliates and the receipt would count a purchase nobody made. It is
     marked paid directly, with `metadata['exchange_of']`.
   - Stock reservation runs through the same `ORDER_RESERVE_STOCK` gate. Fulfilment events
     fire as for any order, so the "on its way" email carries tracking.
   - Revenue reports that filter on paid orders count it at 0.
3. **The cheaper edition's difference** is the paid price of the returned unit less the new
   edition's list price, never below 0. Shipping is not refunded in any outcome, as today.

**Exchange fee** (owner's ask; how it is collected is my call):
- The fee first comes off any difference being refunded.
- What is still owed goes on the exchange order as a fee line, and the order stays unpaid.
  The customer gets A8's payment link (`/pay/<public_token>/`, sent through the seam A8 uses).
  The stock stays reserved, and the new edition ships once that order is paid. The unpaid-order
  sweep cancels it at its payment deadline, and then the return is refunded instead.
- A charged exchange order fires `ORDER_PAID` when the customer pays, since that money is real.
  A free one never does.
4. **Outcomes offered.** A refund is always offered: `refund_full` says whether the full price
   comes back, not whether a refund exists. Store credit is offered only with
   `refund_store_credit`, and exchange only with `refund_exchange`. The published terms then
   match the form.
5. **Who sees a return.**
   - The status page answers the order's owner while signed in.
   - It also answers anyone holding the order's `public_token` in the link (the emails carry
     it), the same rule as the withdrawal pages.
   - A guest who lost the link starts again with order number + email, which lists that
     order's returns.
   - Permission tests cover anonymous without token, the wrong token, another customer, the
     owner and the token.
6. **Returns opened before C4** have no `ReturnResolution`. "Mark received" preselects a
   refund for them, and the new line and window checks apply only to new requests.
7. **Old paths (my call).** returns_portal takes over the same customer paths:
   `/account/orders/<n>/return/`, `/account/returns/` and `/account/returns/<id>/`. Bookmarks
   and old emails keep working; guests get `/returns/`. With the app off, the paths 404, and
   the order page shows no return state.
8. **Exchange that cannot be made.**
   - When some editions are gone or out of stock at "Mark received", those lines are refunded.
   - If none can be made, the whole return is refunded.
   - The closing email says which, line by line.
   - An exchange order is not returnable online (my call): a fault with the replacement goes
     to the store, which handles it from the dashboard.
9. **Dashboard seam (my call).**
   - `ReturnService.close(outcome='exchange')` takes the editions as an argument, so orders
     never reads returns_portal.
   - The dashboard offers "exchange" only when the return carries a chosen exchange, which
     returns_portal supplies through the panel hook. With the app off, staff see refund and
     store credit only.

## What's left to the builder

- The exact page layout in each theme. Follow the withdrawal pages' look.
- Wording of the emails and pages, in the house style (plain words, no developer terms).
- Whether `_goods_start` is moved or imported.
- The name of the dashboard hook.
- The rate limit on the guest lookup. Reuse `returns_portal.views._throttled`.
