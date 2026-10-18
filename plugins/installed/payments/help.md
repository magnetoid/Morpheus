---
summary: Takes payment at checkout through Stripe or PayPal, and routes every refund back through whichever gateway charged the order.
---

## What it's for

This app is what lets your store actually get paid: it offers Stripe and PayPal at checkout, creates the charge, and later issues a refund through whichever one took the money. A method only appears at checkout once it is switched on and fully set up — a shopper is never shown a way to pay that would fail.

## Set it up

Add your Stripe secret key, public key, and webhook secret on [Payment gateways](settings:payments) to take card payments. To also offer PayPal, turn it on and add its client ID, secret, and webhook ID. Until at least one of these is set up, checkout has no way to take payment — [Advanced payments](app:advanced_payments) adds cash on delivery and a sandbox method as another option.

## Common tasks

- Add or update Stripe and PayPal credentials.
- Switch PayPal on or off, and choose sandbox or live mode.
- Mark a cash-on-delivery or bank-transfer order as paid once payment arrives by other means.
- Refund an order, from its own page or by asking Linda.

## Good to know

A refund can only go through automatically when the order was actually charged through Stripe or PayPal; an order taken by cash on delivery, bank transfer, or a sandbox payment has no charge to reverse, so refunding it is recorded but does not move any money — settle those outside the store. Saved cards let a returning customer check out faster without re-entering their details.
