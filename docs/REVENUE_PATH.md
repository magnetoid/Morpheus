# Going-live checklist for dotbooks.store (or your own fork)

A real Morpheus install needs three credentials before it can transact
through Stripe with email confirmations. Each is **out of band** —
they need account-holder action and aren't safe to script.

## 1. Stripe — payment provider

Status: code is wired (`useCompleteOrder()` returns
`paymentClientSecret`; webhook endpoint at `/payments/stripe/webhook/`),
but the keys are placeholder.

**What you need:**

```bash
# In .env on the deploy host, or set via Coolify env panel
STRIPE_PUBLIC_KEY=pk_test_...        # client-side; safe to expose
STRIPE_SECRET_KEY=sk_test_...        # server-side; never ship to git
STRIPE_WEBHOOK_SECRET=whsec_...      # set after creating webhook below
```

**Steps:**

1. Sign up / log in at <https://dashboard.stripe.com>.
2. Toggle **Test mode** in the top right.
3. Copy the test publishable + secret keys from `Developers → API keys`.
4. Create a webhook endpoint pointing at
   `https://YOUR-DOMAIN/payments/stripe/webhook/`. Listen for
   `payment_intent.succeeded`, `payment_intent.payment_failed`, and
   `charge.refunded`.
5. Copy the webhook signing secret.
6. Restart the `web` container.

**Verify:** place a test order with card `4242 4242 4242 4242`, any
future expiry, any CVC. The order should land in `dashboard/orders/`
in `paid` state.

## 2. Email — order confirmations & OTP login

Status: backend defaults to console (logs every email to stdout).
Order confirmations and OTP login codes are visible via
`docker compose logs web | grep "Subject:"` but never reach a real inbox.

**What you need:** any SMTP provider — Postmark, Resend, SendGrid,
Mailgun, AWS SES.

```bash
# In .env on the deploy host
EMAIL_HOST=smtp.postmarkapp.com
EMAIL_PORT=587
EMAIL_HOST_USER=YOUR_POSTMARK_TOKEN
EMAIL_HOST_PASSWORD=YOUR_POSTMARK_TOKEN     # Postmark uses the same value for both
DEFAULT_FROM_EMAIL=hello@YOUR-DOMAIN
```

**Verify:** trigger an OTP login at `/auth/otp/`; the code should
arrive in your inbox within seconds.

## 3. Mobile / Lighthouse pass

Status: never run on a real device. The lazy-loading + standalone
output build are in place, but no measurement.

**What you do:**

1. Open Chrome DevTools → Lighthouse on `https://YOUR-DOMAIN/`.
2. Run the mobile audit.
3. Patch the first three issues it flags. Likely candidates:
   above-the-fold image LCP, missing `<meta name="viewport">`,
   CLS from Fraunces font swap.
4. Re-run; aim for ≥85 across the board.

## 4. PostToolUse hooks

Status: `CLAUDE.md` declares hooks as the enforcement layer but none
are wired in `~/.claude/`. Advisory rules only.

**What you do:** add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {"type": "command", "command": "ruff check $TOOL_INPUT_path"},
          {"type": "command", "command": "ruff format --check $TOOL_INPUT_path"}
        ]
      }
    ]
  }
}
```

This applies *to your Claude Code session*; it isn't repo state, so it
doesn't get committed. Ship a copy in `docs/hooks-example.json` if your
team wants a shared baseline.
