---
summary: Adds two more ways to pay at checkout: cash on delivery, and a sandbox method for testing.
---

## What it's for

This app adds two extra payment methods alongside Stripe and PayPal: cash on delivery, for orders paid when they arrive, and a sandbox "test payment" that always succeeds so staff can try checkout without charging a real card.

## Set it up

Turn cash on delivery on or off and write the instructions shown to the shopper at checkout, such as what the courier collects, on [Advanced payments](settings:advanced_payments). Turn test payment on only while you need it — it is offered to signed-in staff alone, so a shopper never sees a method that takes no money — and switch it off again once the store is live.

## Common tasks

- Turn cash on delivery on or off, and edit its checkout instructions.
- Turn the sandbox test payment on while setting up the store, and off again before going live.
- Sign in as staff and choose "Test payment" at checkout to confirm the rest of checkout works.

## Good to know

Neither method takes a real charge, so neither can be refunded through the usual refund flow — a cash-on-delivery order is settled by whatever was collected on delivery, outside the store. Turning this app off removes both methods from checkout immediately.
