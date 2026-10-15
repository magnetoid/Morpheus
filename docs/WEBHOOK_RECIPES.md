# Webhook recipes

How to wire Morpheus webhooks into common external systems. Every recipe assumes you've already created the endpoint in `/dashboard/apps/webhooks_ui/` with HMAC-SHA256 signing enabled.

## Signature verification

Every webhook carries `X-Morpheus-Signature: sha256=<hex>`. Verify before processing:

```python
import hmac, hashlib

def verify(payload_bytes: bytes, header: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(
        secret.encode('utf-8'), payload_bytes, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, header or '')
```

**Body.** The request body is the event's payload as canonical JSON (sorted keys, no spaces); the event name is in the `X-Morpheus-Event` header. A model appears as its identifying fields — `{"id", "model", "order_number"/"sku"/"email"/"name"/"slug"/"status" when it has them}`, never a record dump. Each delivery carries `X-Morpheus-Delivery` (its id in the delivery log) and `X-Morpheus-Attempt`. Since v0.113.0 every endpoint receives one POST per event, after the transaction commits, and redirects are not followed.
  ```

- **`docs/MIGRATING.md`.** Insert after the intro's `---` line:

  ```
  ## v0.113.0 — one webhook per event, in one shape

  A merchant webhook endpoint used to receive each event twice: once from core, as the bare payload, and once from the Webhooks app, as `{"event": …, "data": …}`, sometimes before the order was saved. It now receives one POST, after commit, whose body is the bare payload (canonical JSON) with the event name in `X-Morpheus-Event`. A receiver that read `body["event"]` or `body["data"]` reads the header and the body itself. Webhook targets must be public hosts and redirects are not followed — point an endpoint at its final URL.
  ```

- **`docs/API_STABILITY.md`.** Add a row at the top of the "Breaking changes shipped" table:

  ```
  | **v0.113.0** | Merchant webhooks | One POST per event after commit (was two, one possibly before commit); the body is the bare payload (the `{"event","data"}` envelope is gone); redirects are not followed and private hosts are refused. | [`MIGRATING.md`](MIGRATING.md#v01130--one-webhook-per-event-in-one-shape) |
  ```

- **The spec.** Change its `**Status:**` line to `**Status:** shipped in v0.113.0.`

- [ ] **Step 3: Cut the release**

Run:

Reject anything that fails verification. Morpheus's outbound retry policy is exponential backoff up to 24h, so a flapping verifier won't lose events.

## Available events

- `order.placed` — cart converted to Order; `payment_status: pending`
- `order.paid` — Stripe `payment_intent.succeeded` confirmed
- `order.cancelled`, `order.refunded`
- `fulfillment.shipped`, `fulfillment.delivered`
- `product.created`, `product.updated`, `product.low_stock`, `product.back_in_stock`
- `customer.registered`, `customer.login`
- `cart.abandoned` — fires 60 minutes after last interaction
- `return.requested`, `return.refunded`

## Recipe 1: Zapier — Slack on every paid order

```
Trigger:  Webhooks by Zapier → Catch Hook
Filter:   event_type contains "order.paid"
Action:   Slack → Send Channel Message
Body:     ":moneybag: New order *{{order.order_number}}*: 
          {{order.total.amount}} {{order.total.currency}}
          from {{order.customer.email}}"
```

Point the Catch Hook URL at Morpheus's webhook endpoint. Done in 4 minutes.

## Recipe 2: n8n — restock email when product is back in stock

```
Trigger:  Webhook (POST, capture body)
Filter:   event_type == "product.back_in_stock"
Action 1: Postgres → SELECT email FROM wishlist_items
          WHERE product_id = $1
Action 2: SMTP → Send to each row
Subject:  "{{product.name}} is back!"
```

## Recipe 3: Make.com — sync paid orders into a Google Sheet

```
Trigger:  Webhook (custom)
Filter:   event_type == "order.paid"
Action:   Google Sheets → Add a Row
Columns:  order_number, customer.email, total.amount,
          total.currency, line_items.length, created_at
```

Morpheus sends one webhook per order; idempotency on your side is `order.id`.

## Recipe 4: Plain `curl` for a self-hosted listener

```bash
# In your listener (Flask/Express/whatever)
@app.post("/morph-hook")
def morph_hook():
    sig = request.headers.get("X-Morpheus-Signature", "")
    if not verify(request.data, sig, SECRET):
        return "bad signature", 401
    event = request.json
    if event["event_type"] == "order.paid":
        ship_it(event["order"])
    return "", 200
```

## Recipe 5: Stripe → Morpheus reverse-flow

Morpheus webhook handling for INBOUND Stripe events is at `/api/payments/stripe/webhook/`. The handler:

1. Writes to `StripeWebhookEvent` first (unique constraint on `stripe_event_id` makes the call idempotent).
2. Routes by `event.type` to `_mark_transaction_success` / `_mark_transaction_failed` (both `atomic()` + `select_for_update()`).
3. Returns 200 only after the side effects commit.

So if you're receiving these on your own infrastructure for analytics, just *also* point Stripe at us and consume the resulting `order.paid` event downstream. One source of truth.

## Replay + retry

`/dashboard/apps/webhooks_ui/deliveries/` shows every outbound attempt with status, response body, and a "Replay" button. Failed deliveries follow the retry schedule:

| Attempt | After |
|---|---|
| 1 | immediate |
| 2 | 30 s |
| 3 | 2 min |
| 4 | 10 min |
| 5 | 1 h |
| 6 | 6 h |
| 7 (final) | 24 h |

After the 7th attempt the delivery is marked `failed` and the merchant gets a one-shot dashboard notification.

## Contributing recipes

Open a PR adding to this file. The bar: must be a real integration you've actually wired up, with the trigger + filter + action + sample payload included.
