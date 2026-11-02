---
summary: Takes payment by Stripe, PayPal or cash on delivery, refunds through the gateway that charged, and scores every new order for fraud.
---

## What it's for

This app is what lets your store get paid: it offers Stripe, PayPal and cash on delivery at checkout, creates the charge, and later refunds through whichever one took the money. A method appears at checkout only once it is switched on and fully set up, so a shopper is never shown a way to pay that would fail. A "test payment" that always succeeds lets staff try checkout without charging a card.

It also checks every new order for signs of fraud: many orders in a short time from one IP address or email, shipping and billing countries that differ, a history of refunds, or a first-time customer placing an unusually large order. Each sign adds to a score from 0 to 100, shown in a Fraud check card on the order's page.

## Set it up

Add your Stripe secret key, public key and webhook secret on [Payment gateways](settings:payments) to take card payments. To offer PayPal, turn it on and add its client ID, secret and webhook ID. On the same page, turn cash on delivery on or off and write the instructions shown at checkout, such as what the courier collects. Turn test payment on only while you need it: only signed-in staff see it, and it should be off once the store is live.

The fraud check needs nothing. You can change the amount above which a first order counts as unusually large (500 by default) on [Payment gateways](settings:payments).

## Common tasks

- Add or update Stripe and PayPal credentials.
- Turn cash on delivery on or off, and edit its instructions.
- Choose "Test payment" at checkout, signed in as staff, to try the rest of checkout.
- Mark a cash-on-delivery or bank-transfer order as paid once the money arrives.
- Refund an order, from its own page or by asking Linda.
- Read an order's fraud score and its reasons on its page, or ask Linda.

## Good to know

A refund moves money only when the order was charged through Stripe or PayPal. For cash on delivery, bank transfer or a test payment it is recorded, and you settle it outside the store.

The fraud score only informs you: no order is held or cancelled because of it. Orders placed before the check was added have no score.
