---
summary: States your return window to search engines and shows a start-a-return link; return requests themselves are handled by Orders.
---

## What it's for

This app's job today is narrow: it tells search engines and shopping feeds your real return window, and it adds a "start a return" link to a shopper's account. The actual return request — getting an RMA number, approving it, and refunding it — is handled by [Orders](app:orders), not by this app.

## Set it up

Set how many days a customer has to return something on [Returns portal](settings:returns_portal). Leaving it at zero states, truthfully, that you take no returns.

You can also say who pays to send a return back ([](field:returns_portal.return_fees)), how items can come back (by post, in a shop or at a kiosk) and which refunds you give (a full refund, an exchange or store credit). Search engines read each one only once you set it. A fixed fee is stated only with its amount ([](field:returns_portal.return_shipping_fee)).

## Good to know

This app does not yet add its own screen for a customer to choose a refund, an exchange, or store credit, or to leave feedback about why they are returning something — those parts are not built, even though they are part of its original idea. What is live is the return window itself: it is published correctly wherever your store states its policies, and it is left out entirely if your store's country is not set.

The same window is the one product pages state, in themes that show a returns line; at zero the line disappears. It is published only for goods you ship: a download, an experience or a service carries no return policy, and a store that sells no goods publishes none.
