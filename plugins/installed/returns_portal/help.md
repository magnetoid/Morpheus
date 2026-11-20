---
summary: Lets customers withdraw from an order online, as EU law asks, and states your return window to search engines.
---

## What it's for

This app does two jobs. It gives customers the "Withdraw from contract here" function EU law has asked for since 19 June 2026, and it tells search engines and shopping feeds your real return window. The return itself (its RMA number, approving it, the refund) is handled by [Orders](app:orders).

## Set it up

Switch the function on with [](field:returns_portal.withdrawal_function) on [Returns portal](settings:returns_portal). The order email then carries the link, and so do the customer's order page and your footer. The period is 14 days ([](field:returns_portal.withdrawal_days)); you can give more, never less.

Set how many days a customer has to return something there too. Leaving it at zero states, truthfully, that you take no returns. You can also say who pays to send a return back ([](field:returns_portal.return_fees)), how items can come back and which refunds you give; search engines read each one only once you set it. A fixed fee is stated only with its amount ([](field:returns_portal.return_shipping_fee)).

## Common tasks

- See who withdrew: each one is on the order's timeline, and Linda can list them.
- Record a withdrawal a customer sent by email, letter or phone: ask Linda, who asks for your yes first.

## Good to know

A withdrawal takes two steps: the customer fills in their name, the order number and their email, then confirms. They get an email with the date and time it was received. An order none of which has left is cancelled and paid back in full; otherwise a return opens for the goods. A service, or a download whose buyer waived the right at checkout, cannot be withdrawn from. The period counts from delivery, or from the order for a download.

A guest's details are checked only once they confirm, and the last page reads the same whether or not they named an order, so nobody learns about someone else's order. While a store in the EU has the function off, the setup checklist and the nightly health check say so. The check also fails while the store has no sending email, since the acknowledgement would reach nobody.

The return window is published only for goods you ship, and left out if your store's country is not set.
