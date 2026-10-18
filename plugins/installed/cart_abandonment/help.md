---
summary: Spots carts shoppers left behind and sends up to three reminder emails to bring them back, only to shoppers who allow marketing email.
---

## What it's for

When a shopper adds items to their cart and leaves without buying, this app notices and can send a short series of reminder emails to bring them back — up to three, spaced further apart each time. It works for guests who typed an email at checkout, not just signed-in customers.

## Set it up

The reminder sequence is on by default. Open [Cart recovery](settings:cart_abandonment) to turn it off ([](field:cart_abandonment.recovery_enabled)), require a shopper's marketing consent before emailing them ([](field:cart_abandonment.require_marketing_consent)), or change the timing: how long before a cart counts as abandoned ([](field:cart_abandonment.abandon_after_minutes)) and the delay before each reminder ([](field:cart_abandonment.step_delays_minutes)). The wording of each reminder email can be edited from the store's email template list.

## Common tasks

- Turn the recovery emails on or off for the whole store.
- Change how long to wait before a cart counts as abandoned.
- Change the delay before each of the three reminders.
- Require that a shopper has agreed to marketing email before sending to them.

## Good to know

A shopper needs a reachable email address to be sent a reminder — by default, carts with none are skipped. Every reminder carries a one-click unsubscribe link; a shopper who uses it never gets another cart-recovery email. The store checks for newly abandoned carts every 30 minutes and checks whether a reminder is due every 15 minutes.
