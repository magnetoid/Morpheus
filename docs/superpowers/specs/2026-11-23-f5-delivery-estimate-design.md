# F5 · Delivery estimate at checkout — design

Approved by the owner on 2026-11-23. This is a small change: row F5 of `docs/plans/platform-gap-analysis-2026-11.md`, released as a patch.

## Intent

A shopper should see how long delivery takes before they choose a rate, and see the same promise again after ordering. The numbers come from the rate's fastest and slowest delivery days plus the store's handling time. These are the values the structured data already publishes, so the page and the graph never disagree.

## Goals

- **Checkout's shipping choices.** Each rate shows a business-day range under its name, for example "3–7 business days". This holds in all six themes (dot_books, montenegro, croatia, supernatural_shop, irving_survival, dawnchild) and in both checkout forms (`checkout_shipping.html` and `checkout_one_page.html`).
- **How the range is computed.** Range = handling days + transit days, low end with low end and high end with high end.
  - Transit days are read the way `shipping/seo_graph.py:_transit_days` reads them: a lone min or a lone max stands for both ends.
  - Handling days come from `seo_graph.handling_days()`. When no handling time is set, the range is transit only.
  - A rate with neither transit value shows nothing.
  - When both ends are equal, it shows "3 business days".
- **The promise is saved on the order.** When the order is placed, the estimate for the chosen rate is stamped on the order (`Order.metadata['delivery_estimate'] = {'min': int, 'max': int}`), the same way tax lines travel today. The buyer's order page in each theme (`account_order_detail.html` and the `order_confirmation.html` thank-you page) and the placed email (`order_placed.html` and `.txt`) show the stamp. A later edit to the rate never changes what an order says.
- **Setting.** `show_delivery_estimate` is a shipping setting, default off. It sits on the Shipping page next to the handling time. While it is off, nothing is shown and nothing is stamped. Linda changes it through the existing `settings.set`.
- **Translations.** The text is translated for sr and hr.

## Non-goals and anti-goals

- No calendar dates, and no holidays or cut-off maths. A wrong date is a broken promise.
- No estimate on the wallet sheet (Apple Pay and Google Pay express checkout).
- No change to the structured data.
- A theme or the storefront shell never imports shipping. The checkout text arrives on the rate dict from shipping's `CHECKOUT_SHIPPING_RATES` answer. The order stamp arrives through the cart breakdown `meta`, which orders copies into metadata. Orders shows it through a property on Order that reads its own metadata.

## Approaches considered

1. **Picked: stamp at placement, show from the order.** What was promised stays what was promised.
2. Recompute from the current rate on the order page and in the email. This is simpler, but the promise drifts when the merchant edits a rate.
3. Calendar dates. These read better, but they need holidays and the cut-off, and a wrong date breaks trust.

## Left to the builder

- Exact markup and styling per theme. It should match each theme's existing small or meta text.
- The property name on Order.
- Test layout. Planned tests:
  - `themes/test_delivery_estimate.py`: every theme, both checkout forms, plus the order page and the email;
  - a shipping unit test for the range rules.
- The help.md update for shipping.
