---
name: morpheus-orders
description: >-
  Orders on a Morpheus store: finding an order, fulfilment and shipping,
  cancellations, refunds, and payments that look stuck.
version: 2.0.0
author: Morpheus OS
license: MIT
metadata:
  janus:
    tags: [morpheus, ecommerce, orders, fulfillment]
    related_skills: [morpheus-store-operator, morpheus-catalog]
---

# Morpheus orders

## Read

| Tool | Use |
|---|---|
| `orders.search` | By number, email, status or date; also "latest orders" |
| `orders.get` | One order: lines, money, fulfilment, notes |
| `orders.summary` | A one-order overview by number |
| `returns.list` | Return requests |
| `draft_orders.list` | Draft orders |
| `subscriptions.list` | Subscriptions |

If a search finds nothing, say so.

## Triage

1. Pending: was the payment captured? A charge in the payment provider with the
   order still unpaid usually means a missed payment webhook. Flag it; never
   mark an order paid yourself.
2. Paid, not fulfilled: offer `orders.mark_fulfilled`.
3. Fulfilled, not shipped: offer `orders.mark_shipped` with the tracking number.
4. Refund or cancel requests: name the order number and amount.

## Changes (each needs the merchant's yes)

| Tool | Does |
|---|---|
| `orders.mark_fulfilled` | Fulfil a paid order |
| `orders.mark_shipped` | Ship, with tracking |
| `orders.add_note` | Staff note |
| `orders.update_status` | Other status changes |
| `orders.cancel` | Cancel (releases stock) |
| `orders.refund` | Refund through the payment provider — real money |
| `orders.mark_refunded` | Record a refund made outside the store |
| `returns.approve` | Approve a return and quote the refund |

Describe it first: "Refund order #1042, $42.00, reason: damaged." If the tool
asks for `confirmed` or an echoed order number, supply them in the call you make
after the merchant's yes.

## Pitfalls

1. Cancelling when they asked for a refund: different outcome, different money.
2. Fulfilling an unpaid order.
3. Marking an order refunded because the provider shows a refund, unless asked.
