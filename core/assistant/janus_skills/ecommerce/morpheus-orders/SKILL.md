---
name: morpheus-orders
description: >-
  Orders on a Morpheus store: finding an order, fulfilment and shipping,
  cancellations, refunds, and payments that look stuck.
version: 2.1.0
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
2. Paid, not shipped: offer `orders.fulfill_lines` (a parcel with some or all of
   the open units and its tracking number). `orders.get` lists the parcels
   already sent; downloads never go in a parcel.
3. A carrier is set up (Shippo or EasyPost): offer `shipping.buy_label` for a
   parcel, or for everything left on the order. It spends money.
4. Refund or cancel requests: name the order number and amount.

## Changes (each needs the merchant's yes)

| Tool | Does |
|---|---|
| `orders.fulfill_lines` | Ship a parcel: lines by SKU and quantity (none = all), tracking |
| `shipping.buy_label` | Buy a carrier label for a parcel, or ship what is left with one |
| `orders.mark_fulfilled` | Mark fulfilled without recording a parcel |
| `orders.mark_shipped` | Mark shipped without recording a parcel |
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
4. Shipping with `orders.mark_shipped` when the merchant sends part of an order:
   only `orders.fulfill_lines` records which units left.
