---
summary: Scores every new order for fraud risk in the background; nothing is shown on screen, and no order is held or cancelled automatically.
---

## What it's for

This app quietly checks every order placed in the store for signs of fraud. It looks at how many orders just came from the same IP address or email, whether the shipping and billing countries match, whether the card's first six digits are on a list of known bad numbers, whether the customer has a history of refunds, and whether a first-time customer is placing an unusually large order. Each signal adds to a score from 0 to 100.

## Set it up

Every order is scored automatically; there is nothing to turn on. A [Fraud rules](settings:fraud_rules) page exists under settings, but it has no fields to fill in today, so the list of risky card numbers stays empty and the large-first-order threshold stays fixed at $500.

## Good to know

The score and the reasons behind it are saved on the order itself, but no screen in the dashboard shows them today. Nothing acts on a high score automatically: no order is held, queued for review, or cancelled because of it. An order scoring 60 or above writes one line to the server log; anything below that leaves no trace at all.
