---
name: morpheus-orders
description: >-
  Use when the merchant asks about orders, fulfillment, shipping, cancellations,
  refunds, or stuck checkouts on a Morpheus shop. MCP/Linda tools:
  orders.search/get/summary/list_recent, mark_fulfilled, mark_shipped, cancel,
  refund, add_note.
version: 1.0.0
author: Morpheus OS
license: MIT
metadata:
  janus:
    tags: [morpheus, ecommerce, orders, fulfillment]
    related_skills: [morpheus-store-operator, morpheus-catalog]
---

# Morpheus orders

Operate the order book for this shop. Merchant-facing name stays **Linda**.

## When to Use

- "Where is order …", "fulfill/ship this", "refund", "cancel", "unpaid"
- Daily: unfulfilled, awaiting shipment, failed payments

Do not use for catalog/stock except to mention a line item is out of stock.

## Read first

| Tool | Use |
|---|---|
| `orders.search` | Query by number, email, status, date |
| `orders.get` | One order — line items, money, fulfillment, notes |
| `orders.list_recent` | Latest N for a pulse |
| `orders.summary` | Counts / revenue snapshot |

Never invent totals. If search returns 0, say 0.

## Daily triage

1. Unpaid / pending — payment captured? Stripe webhook missing means charge
   taken but order still unpaid (stock not decremented). Flag, don't silently
   mark paid.
2. Paid + unfulfilled — offer `orders.mark_fulfilled`.
3. Fulfilled + not shipped — `orders.mark_shipped` with tracking if they have it.
4. Refund / cancel requests — hard-gated. Echo the **order number** and amount.

## Writes

| Tool | What it does | Gate |
|---|---|---|
| `orders.mark_fulfilled` / `markOrderFulfilled` | FSM fulfill() | confirm |
| `orders.mark_shipped` / `markOrderShipped` | ship() + tracking | confirm |
| `orders.add_note` | Staff note on the order | confirm |
| `orders.update_status` | Status change | confirm |
| `orders.cancel` / `cancelOrder` | FSM cancel() | **hard-gate** |
| `orders.refund` / `orders.mark_refunded` | Real money | **hard-gate** |

Pattern: describe the change (`I'm refunding #1042, $42.00, reason: …`) → wait
for yes → re-call with `confirmed=True` and `hard_gate_ack="YES"` plus the
echoed order number when the tool asks for it.

Do not mark refunded because an external Stripe dashboard shows a refund
unless the merchant asked you to sync state.

## Buy-path reminder (when payments look stuck)

Live checkout is `/checkout/` or `/checkout/quick/` → GraphQL `completeOrder`
→ Stripe Payment Element → `POST /payments/webhooks/stripe/`. Missing webhook
secret = paid in Stripe, unpaid in Morpheus. `checkout_experience` is not the
buy path.

## Common Pitfalls

1. Refunding without echoing the order number.
2. Fulfilling an unpaid order.
3. Cancelling when they asked to refund (different FSM + money).
4. Dumping full customer PII when a last-4 / order number would do.

## Verification Checklist

- [ ] Identified the order by number from a tool
- [ ] State change matches the ask (fulfill vs ship vs cancel vs refund)
- [ ] Hard-gated writes waited for a second explicit yes
