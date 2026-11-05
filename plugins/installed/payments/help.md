---
summary: Takes payment by Stripe, PayPal or cash on delivery, refunds through the gateway that charged, and scores every new order for fraud.
---

## What it's for

This app gets your store paid: it offers Stripe, PayPal and cash on delivery at checkout, takes the charge, and refunds through whichever one took the money. A method appears at checkout only once it is switched on and fully set up. While Stripe is set up, the cart page also shows Apple Pay, Google Pay and Link buttons, so a shopper can pay from their wallet without filling in the checkout form.

It also scores every new order for fraud from 0 to 100, from signs such as many orders from one IP address or email, differing shipping and billing countries, past refunds, or an unusually large first order. The score shows in a Fraud check card on the order's page.

## Set it up

Add your Stripe secret key, public key and webhook secret on [Payment gateways](settings:payments) to take card payments. To offer PayPal, turn it on and add its client ID, secret and webhook ID. On the same page, turn cash on delivery on or off and write the instructions shown at checkout. Turn test payment on only while you need it: only signed-in staff see it.

The fraud check needs nothing. The amount above which a first order counts as unusually large (500 by default) is on the same page.

## Common tasks

- Add or update Stripe and PayPal credentials.
- Turn the wallet buttons on the cart page on or off, or ask Linda.
- Turn cash on delivery on or off, and edit its instructions.
- Try checkout as staff by choosing "Test payment".
- Mark a cash-on-delivery or bank-transfer order as paid once the money arrives.
- Refund an order, from its own page or by asking Linda.
- Read an order's fraud score and its reasons on its page, or ask Linda.

## Good to know

A wallet order is placed only for the total the wallet showed, with your shipping rates and tax. A declined wallet payment finishes on the checkout's payment page. A cart holding a download uses the checkout form while the digital-content acknowledgement is on. Apple Pay also needs your domain registered with Stripe.

A refund moves money only for an order charged through Stripe or PayPal; any other refund is recorded, and you settle it outside the store.

The fraud score only informs you: no order is held or cancelled because of it. Orders older than the check have no score.
