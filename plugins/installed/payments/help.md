---
summary: Takes payment by Stripe, PayPal or cash on delivery, refunds through the gateway that charged, and scores every new order for fraud.
---

## What it's for

This app takes payment by Stripe, PayPal or cash on delivery and refunds through whichever one took the money. A method appears at checkout once it is switched on and set up. With Stripe set up, the cart page also shows Apple Pay, Google Pay and Link buttons.

It also scores each new order for fraud from 0 to 100 (many orders from one IP address or email, mismatched countries, past refunds, a large first order) on the order's page.

## Set it up

Add your Stripe secret key, public key and webhook secret on [Payment gateways](settings:payments); PayPal needs its client ID, secret and webhook ID. The same page switches cash on delivery and its instructions, the staff-only test payment, and the amount above which a first order looks large (500 by default).

Cards are charged at checkout, or held and charged with the first parcel, with the last one, or when you press Charge now. A hold older than the days you set (six at most) is charged or given back. Holding needs your Stripe webhook to send "payment_intent.amount_capturable_updated" and "payment_intent.canceled". You can also show signed-in shoppers their saved cards, or offer to save a new one.

## Common tasks

- Turn the cart's wallet buttons on or off.
- Mark a cash-on-delivery or bank-transfer order paid once the money arrives.
- Charge a held card from the Payment panel on its order.
- Refund an order from its page.
- Read an order's fraud score and its reasons.
- Ask Linda to do any of these.

## Good to know

A wallet order is placed only for the total the wallet showed; a declined one finishes on the payment page. A cart with a download uses the checkout form while the digital-content acknowledgement is on. Apple Pay also needs your domain registered with Stripe.

Cash on delivery is offered only when everything in the cart ships.

Only Stripe and PayPal refunds move money; for other orders the refund form adds the amount to store credit, records it as paid back, or leaves it to settle by hand.

A held payment cannot be marked paid or refunded until it is charged; cancelling the order gives it back. An order with a download is charged at checkout. A declined card is noted on the order's timeline.

The fraud score only informs you: no order is held or cancelled because of it.
